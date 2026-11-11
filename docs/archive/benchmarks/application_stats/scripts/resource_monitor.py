"""
resource_monitor.py
===================
psutil-based CPU and memory sampler for QCanvas backend resource profiling.
Used by nb03_resource_usage.ipynb.
"""

import os
import sys
import time
import threading
import tracemalloc
from dataclasses import dataclass, field
from typing import Any

import psutil
import httpx

BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT = 90.0


# ── Structures ────────────────────────────────────────────────────────────────

@dataclass
class ResourceSample:
    timestamp: float
    cpu_percent: float
    rss_mb: float
    vms_mb: float


@dataclass
class ResourceProfile:
    label: str
    samples: list[ResourceSample] = field(default_factory=list)
    start_time: float = 0.0
    end_time: float = 0.0
    request_latency_ms: float = 0.0
    status_code: int = 0
    ok: bool = False

    @property
    def duration_s(self) -> float:
        return self.end_time - self.start_time

    @property
    def peak_cpu(self) -> float:
        return max((s.cpu_percent for s in self.samples), default=0.0)

    @property
    def peak_rss_mb(self) -> float:
        return max((s.rss_mb for s in self.samples), default=0.0)

    @property
    def mean_cpu(self) -> float:
        if not self.samples:
            return 0.0
        return sum(s.cpu_percent for s in self.samples) / len(self.samples)

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "duration_s": round(self.duration_s, 3),
            "request_latency_ms": round(self.request_latency_ms, 2),
            "peak_cpu_pct": round(self.peak_cpu, 2),
            "mean_cpu_pct": round(self.mean_cpu, 2),
            "peak_rss_mb": round(self.peak_rss_mb, 2),
            "status_code": self.status_code,
            "ok": self.ok,
            "n_samples": len(self.samples),
        }


# ── Monitor thread ────────────────────────────────────────────────────────────

class ResourceMonitor:
    """
    Background thread that samples CPU + memory of the *current process*
    (i.e., the Python process making the HTTP call) and optionally a
    target process by PID.

    This monitor tracks resource usage. When running natively (uvicorn), 
    pointing it at the server PID allows for true server-side monitoring.
    """

    def __init__(self, interval_s: float = 0.2, target_pid: int | None = None):
        self.interval_s = interval_s
        self._proc = psutil.Process(os.getpid())
        
        # If no PID provided, we'll try to find uvicorn automatically later
        # or stick to the current process.
        self._target_proc: psutil.Process | None = None
        if target_pid:
            try:
                self._target_proc = psutil.Process(target_pid)
            except psutil.NoSuchProcess:
                print(f"[monitor] Warning: PID {target_pid} not found. Monitoring client instead.")
        
        self._samples: list[ResourceSample] = []
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def set_target_pid(self, pid: int):
        """Manually set a target PID to monitor."""
        try:
            self._target_proc = psutil.Process(pid)
        except psutil.NoSuchProcess:
             print(f"[monitor] Error: PID {pid} not found.")

    def start(self):
        self._samples = []
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> list[ResourceSample]:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        return self._samples

    def _run(self):
        proc = self._target_proc or self._proc
        while not self._stop_event.is_set():
            try:
                cpu = proc.cpu_percent(interval=None)
                mem = proc.memory_info()
                self._samples.append(
                    ResourceSample(
                        timestamp=time.time(),
                        cpu_percent=cpu,
                        rss_mb=mem.rss / 1024 / 1024,
                        vms_mb=mem.vms / 1024 / 1024,
                    )
                )
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            time.sleep(self.interval_s)


# ── Profiled HTTP call ────────────────────────────────────────────────────────

def profile_request(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    json: Any = None,
    label: str = "",
    sample_interval_s: float = 0.05,
    target_pid: int | None = None,
) -> ResourceProfile:
    """
    Make a single HTTP request while sampling CPU/memory in the background.
    Returns a ResourceProfile with timing, CPU, and memory stats.
    """
    profile = ResourceProfile(label=label or url)
    monitor = ResourceMonitor(interval_s=sample_interval_s, target_pid=target_pid)

    monitor.start()
    profile.start_time = time.perf_counter()

    t0 = time.perf_counter()
    try:
        resp = httpx.request(
            method,
            url,
            headers=headers or {},
            json=json,
            timeout=DEFAULT_TIMEOUT,
        )
        profile.request_latency_ms = (time.perf_counter() - t0) * 1000
        profile.status_code = resp.status_code
        profile.ok = resp.status_code < 400
    except Exception as exc:
        profile.request_latency_ms = (time.perf_counter() - t0) * 1000
        profile.status_code = -1
        profile.ok = False

    profile.end_time = time.perf_counter()
    profile.samples = monitor.stop()
    return profile


def profile_n_requests(
    method: str,
    url: str,
    *,
    n: int = 5,
    headers: dict | None = None,
    json: Any = None,
    label: str = "",
) -> list[ResourceProfile]:
    """Run profile_request n times and return a list of profiles."""
    profiles = []
    for i in range(n):
        p = profile_request(method, url, headers=headers, json=json, label=f"{label} [run {i+1}]")
        profiles.append(p)
    return profiles


# ── tracemalloc helper ────────────────────────────────────────────────────────

def measure_python_memory(func, *args, **kwargs) -> dict:
    """
    Run a callable and measure its Python heap allocation using tracemalloc.
    Returns peak_mb and current_mb after the call.
    """
    tracemalloc.start()
    try:
        result = func(*args, **kwargs)
    finally:
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
    return {
        "current_mb": current / 1024 / 1024,
        "peak_mb": peak / 1024 / 1024,
        "result": result,
    }


# ── Process Finder Helper ─────────────────────────────────────────────────────

def find_process_by_name(name: str = "uvicorn") -> int | None:
    """
    Search for a running process whose name contains the string.
    Useful for finding the 'uvicorn' PID automatically.
    """
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            # Check name or cmdline (e.g., 'python -m uvicorn')
            info = proc.info
            if name.lower() in (info['name'] or "").lower():
                return info['pid']
            cmdline = " ".join(info['cmdline'] or [])
            if name.lower() in cmdline.lower():
                return info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return None


# ── System snapshot ───────────────────────────────────────────────────────────

def system_snapshot() -> dict:
    """Return a point-in-time snapshot of system resource usage."""
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    return {
        "total_ram_gb": round(mem.total / 1e9, 2),
        "available_ram_gb": round(mem.available / 1e9, 2),
        "ram_used_pct": mem.percent,
        "cpu_count": psutil.cpu_count(),
        "cpu_freq_mhz": (psutil.cpu_freq().current if psutil.cpu_freq() else None),
        "disk_free_gb": round(disk.free / 1e9, 2),
        "python_version": sys.version,
    }
