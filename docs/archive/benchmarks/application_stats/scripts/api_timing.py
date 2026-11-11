"""
api_timing.py
=============
Reusable helpers for timed HTTP calls against the QCanvas backend.
Used by nb01_api_latency.ipynb and nb02_load_test.ipynb.
"""

import time
import asyncio
import statistics
from typing import Any

import httpx
import pandas as pd

# ── Configuration ────────────────────────────────────────────────────────────
BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT = 60.0  # seconds


# ── Auth helpers ─────────────────────────────────────────────────────────────

def get_auth_token(
    email: str = "demo@qcanvas.ai",
    password: str = "demo123",
    base_url: str = BASE_URL,
) -> str | None:
    """Log in and return a JWT token, or None if auth fails."""
    try:
        resp = httpx.post(
            f"{base_url}/api/auth/login",
            json={"email": email, "password": password},
            timeout=DEFAULT_TIMEOUT,
        )
        if resp.status_code == 200:
            data = resp.json()
            return data.get("access_token") or data.get("token")
    except Exception as exc:
        print(f"[auth] Warning: could not obtain token – {exc}")
    return None


def auth_headers(token: str | None) -> dict:
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


# ── Single-request timing ─────────────────────────────────────────────────────

def timed_request(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    json: Any = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> dict:
    """
    Make one HTTP request and return a dict with:
      status_code, latency_ms, ok (bool), response_body
    """
    t0 = time.perf_counter()
    try:
        resp = httpx.request(
            method,
            url,
            headers=headers or {},
            json=json,
            timeout=timeout,
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        return {
            "status_code": resp.status_code,
            "latency_ms": latency_ms,
            "ok": resp.status_code < 400,
            "response_body": resp.text[:500],
        }
    except Exception as exc:
        latency_ms = (time.perf_counter() - t0) * 1000
        return {
            "status_code": -1,
            "latency_ms": latency_ms,
            "ok": False,
            "response_body": str(exc),
        }


# ── Multi-sample timing ────────────────────────────────────────────────────────

def benchmark_endpoint(
    method: str,
    url: str,
    *,
    n: int = 20,
    headers: dict | None = None,
    json: Any = None,
    label: str = "",
    warmup: int = 2,
) -> dict:
    """
    Call an endpoint `n` times (after `warmup` discarded calls) and compute
    percentile statistics.

    Returns a summary dict:
      endpoint, n, p50_ms, p90_ms, p95_ms, p99_ms, min_ms, max_ms,
      mean_ms, error_rate
    """
    results = []
    # Warmup
    for _ in range(warmup):
        timed_request(method, url, headers=headers, json=json)

    # Measured runs
    for _ in range(n):
        r = timed_request(method, url, headers=headers, json=json)
        results.append(r)

    latencies = [r["latency_ms"] for r in results]
    errors = sum(1 for r in results if not r["ok"])

    return {
        "endpoint": label or url,
        "n": n,
        "p50_ms": statistics.median(latencies),
        "p90_ms": sorted(latencies)[int(0.90 * len(latencies))],
        "p95_ms": sorted(latencies)[int(0.95 * len(latencies))],
        "p99_ms": sorted(latencies)[int(0.99 * len(latencies))],
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "mean_ms": statistics.mean(latencies),
        "std_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0,
        "error_rate": errors / n,
        "raw_latencies": latencies,
    }


# ── Cold vs warm ──────────────────────────────────────────────────────────────

def cold_vs_warm(
    method: str,
    url: str,
    *,
    headers: dict | None = None,
    json: Any = None,
    n_warm: int = 10,
) -> dict:
    """
    Measure the first (cold) request vs. the mean of `n_warm` subsequent ones.
    """
    cold = timed_request(method, url, headers=headers, json=json)
    warm_latencies = []
    for _ in range(n_warm):
        r = timed_request(method, url, headers=headers, json=json)
        warm_latencies.append(r["latency_ms"])
    return {
        "cold_ms": cold["latency_ms"],
        "warm_mean_ms": statistics.mean(warm_latencies),
        "warm_p95_ms": sorted(warm_latencies)[int(0.95 * len(warm_latencies))],
        "speedup_factor": cold["latency_ms"] / statistics.mean(warm_latencies)
        if warm_latencies
        else None,
    }


# ── Async concurrent timing ────────────────────────────────────────────────────

async def _async_request(
    client: httpx.AsyncClient,
    method: str,
    url: str,
    headers: dict,
    json_body: Any,
) -> dict:
    t0 = time.perf_counter()
    try:
        resp = await client.request(method, url, headers=headers, json=json_body)
        latency_ms = (time.perf_counter() - t0) * 1000
        return {"latency_ms": latency_ms, "ok": resp.status_code < 400, "status": resp.status_code}
    except Exception as exc:
        return {"latency_ms": (time.perf_counter() - t0) * 1000, "ok": False, "status": -1}


async def concurrent_burst(
    method: str,
    url: str,
    *,
    n_concurrent: int = 10,
    headers: dict | None = None,
    json: Any = None,
) -> dict:
    """Fire `n_concurrent` requests at the same time and collect results."""
    async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
        tasks = [
            _async_request(client, method, url, headers or {}, json)
            for _ in range(n_concurrent)
        ]
        results = await asyncio.gather(*tasks)

    latencies = [r["latency_ms"] for r in results]
    errors = sum(1 for r in results if not r["ok"])
    return {
        "n_concurrent": n_concurrent,
        "mean_ms": statistics.mean(latencies),
        "p95_ms": sorted(latencies)[int(0.95 * len(latencies))],
        "max_ms": max(latencies),
        "error_rate": errors / n_concurrent,
        "throughput_rps": n_concurrent / (max(latencies) / 1000),
    }


def run_concurrency_sweep(
    method: str,
    url: str,
    *,
    levels: list[int] | None = None,
    headers: dict | None = None,
    json: Any = None,
) -> pd.DataFrame:
    """
    Run concurrent_burst at each concurrency level and return a DataFrame
    suitable for plotting.
    """
    if levels is None:
        levels = [1, 2, 5, 10, 20, 30, 50]
    rows = []
    for n in levels:
        result = asyncio.run(
            concurrent_burst(method, url, n_concurrent=n, headers=headers, json=json)
        )
        result["concurrency"] = n
        rows.append(result)
    return pd.DataFrame(rows)


# ── Pre-built endpoint catalogue ───────────────────────────────────────────────

def get_endpoint_catalogue(token: str | None, base_url: str = BASE_URL) -> list[dict]:
    """
    Returns a list of (method, url, json_body, label) dicts for all key endpoints.
    """
    hdrs = auth_headers(token)

    return [
        # ── Health (baseline) ──
        {
            "method": "GET",
            "url": f"{base_url}/api/health",
            "json": None,
            "headers": {},
            "label": "GET /api/health",
        },
        # ── Auth ──
        {
            "method": "POST",
            "url": f"{base_url}/api/auth/login",
            "json": {"email": "demo@qcanvas.ai", "password": "demo123"},
            "headers": {},
            "label": "POST /api/auth/login",
        },
        # ── Converter (Cirq) ──
        {
            "method": "POST",
            "url": f"{base_url}/api/converter/convert",
            "json": {
                "code": (
                    "import cirq\n"
                    "q0, q1 = cirq.LineQubit.range(2)\n"
                    "circuit = cirq.Circuit([\n"
                    "    cirq.H(q0),\n"
                    "    cirq.CNOT(q0, q1),\n"
                    "    cirq.measure(q0, q1, key='result')\n"
                    "])"
                ),
                "framework": "cirq",
            },
            "headers": hdrs,
            "label": "POST /api/converter/convert (Cirq Bell)",
        },
        # ── Converter (Qiskit) ──
        {
            "method": "POST",
            "url": f"{base_url}/api/converter/convert",
            "json": {
                "code": (
                    "from qiskit import QuantumCircuit\n"
                    "qc = QuantumCircuit(2, 2)\n"
                    "qc.h(0)\n"
                    "qc.cx(0, 1)\n"
                    "qc.measure([0, 1], [0, 1])"
                ),
                "framework": "qiskit",
            },
            "headers": hdrs,
            "label": "POST /api/converter/convert (Qiskit Bell)",
        },
        # ── Converter (PennyLane) ──
        {
            "method": "POST",
            "url": f"{base_url}/api/converter/convert",
            "json": {
                "code": (
                    "import pennylane as qml\n"
                    "dev = qml.device('default.qubit', wires=2)\n"
                    "@qml.qnode(dev)\n"
                    "def bell_state():\n"
                    "    qml.Hadamard(wires=0)\n"
                    "    qml.CNOT(wires=[0, 1])\n"
                    "    return qml.probs(wires=[0, 1])"
                ),
                "framework": "pennylane",
            },
            "headers": hdrs,
            "label": "POST /api/converter/convert (PennyLane Bell)",
        },
        # ── Simulator (small circuit) ──
        {
            "method": "POST",
            "url": f"{base_url}/api/simulator/simulate",
            "json": {
                "qasm_code": (
                    "OPENQASM 3.0;\n"
                    "qubit[2] q;\n"
                    "bit[2] c;\n"
                    "h q[0];\n"
                    "cx q[0], q[1];\n"
                    "c[0] = measure q[0];\n"
                    "c[1] = measure q[1];\n"
                ),
                "backend": "statevector",
                "shots": 1024,
            },
            "headers": hdrs,
            "label": "POST /api/simulator/simulate (statevector 2q)",
        },
        # ── Projects list ──
        {
            "method": "GET",
            "url": f"{base_url}/api/projects",
            "json": None,
            "headers": hdrs,
            "label": "GET /api/projects",
        },
    ]
