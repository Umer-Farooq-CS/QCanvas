#!/usr/bin/env python3
"""
Startup script for QCanvas Backend

Environment:
  WEB_CONCURRENCY             uvicorn worker processes (default: min(4, CPUs), also
                              capped by the container memory limit, see below)
  WORKER_MEMORY_MB            RAM budget per worker used for that cap (default 1000;
                              each worker imports cirq/qiskit/pennylane: ~0.5-1 GB)
  HOST / PORT                 bind address (default 0.0.0.0:8000)
  PROXY_HEADERS               trust X-Forwarded-* headers (default true)
  FORWARDED_ALLOW_IPS         proxies trusted for X-Forwarded-* (default "*": we sit
                              behind a load balancer whose address isn't fixed)
  UVICORN_TIMEOUT_KEEP_ALIVE  seconds; must exceed the load balancer's idle timeout
                              (ALB default 60s) or the LB intermittently gets 502s
                              from reusing connections uvicorn already closed (default 75)
  UVICORN_LOG_LEVEL           default "info"
  UVICORN_ACCESS_LOG          default true
"""
import os
import sys

BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _read_first_line(path: str):
    try:
        with open(path) as fh:
            return fh.readline().strip()
    except OSError:
        return None


def available_cpus() -> int:
    """CPUs this process may use, honouring cgroup CPU quotas (Docker/ECS)."""
    try:
        count = len(os.sched_getaffinity(0))  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        count = os.cpu_count() or 1

    quota = None
    cpu_max = _read_first_line("/sys/fs/cgroup/cpu.max")  # cgroup v2: "<quota> <period>"
    if cpu_max:
        parts = cpu_max.split()
        if len(parts) == 2 and parts[0] != "max":
            try:
                quota = float(parts[0]) / float(parts[1])
            except (ValueError, ZeroDivisionError):
                quota = None
    else:  # cgroup v1
        q = _read_first_line("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
        p = _read_first_line("/sys/fs/cgroup/cpu/cpu.cfs_period_us")
        try:
            if q and p and int(q) > 0:
                quota = int(q) / int(p)
        except ValueError:
            quota = None

    if quota:
        count = min(count, max(1, int(quota + 0.5)))
    return max(1, count)


def memory_limit_mb():
    """Container memory limit in MB, or None if unlimited/unknown."""
    for path in ("/sys/fs/cgroup/memory.max", "/sys/fs/cgroup/memory/memory.limit_in_bytes"):
        raw = _read_first_line(path)
        if raw and raw != "max":
            try:
                value = int(raw)
            except ValueError:
                continue
            if 0 < value < (1 << 60):  # v1 reports a huge number when unlimited
                return value // (1024 * 1024)
    return None


def default_workers() -> int:
    workers = min(4, available_cpus())
    mem_mb = memory_limit_mb()
    if mem_mb:
        per_worker = int(os.getenv("WORKER_MEMORY_MB", "1000"))
        # Keep ~500 MB headroom for the supervisor process and simulation spikes.
        workers = min(workers, max(1, (mem_mb - 500) // max(per_worker, 1)))
    return max(1, workers)


def resolve_workers() -> int:
    raw = os.getenv("WEB_CONCURRENCY", "").strip()
    if raw:
        try:
            return max(1, int(raw))
        except ValueError:
            print(f"Ignoring invalid WEB_CONCURRENCY={raw!r}")
    return default_workers()


def main() -> None:
    import uvicorn

    workers = resolve_workers()
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8000"))

    options = dict(
        host=host,
        port=port,
        reload=False,
        log_level=os.getenv("UVICORN_LOG_LEVEL", "info"),
        access_log=_env_bool("UVICORN_ACCESS_LOG", True),
        proxy_headers=_env_bool("PROXY_HEADERS", True),
        forwarded_allow_ips=os.getenv("FORWARDED_ALLOW_IPS", "*"),
        timeout_keep_alive=int(os.getenv("UVICORN_TIMEOUT_KEEP_ALIVE", "75")),
    )

    print("Starting QCanvas Backend...")
    print(f"Workers: {workers} (CPUs available: {available_cpus()}, memory limit: {memory_limit_mb() or 'unlimited'} MB)")
    print(f"API Documentation will be available at: http://localhost:{port}/docs")
    print(f"Health check: http://localhost:{port}/api/health")

    if workers > 1:
        # Multiple processes require an import string; each worker imports the app
        # (and cirq/qiskit/pennylane) itself, so the supervisor stays small.
        uvicorn.run("app.main:app", workers=workers, app_dir=BACKEND_DIR, **options)
    else:
        from app.main import app

        uvicorn.run(app, **options)


if __name__ == "__main__":
    main()
