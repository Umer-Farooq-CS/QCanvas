"""
batch_converter.py
==================
Loads all circuits from fixtures/example_circuits.json and runs each one
through the QCanvas conversion and simulation pipeline.
Used by nb04_conversion_success.ipynb.
"""

import json
import time
from pathlib import Path
from typing import Any

import httpx

BASE_URL = "http://localhost:8000"
DEFAULT_TIMEOUT = 120.0
FIXTURES_PATH = Path(__file__).parent.parent / "fixtures" / "example_circuits.json"

# A minimal valid QASM snippet used as fallback for simulation when conversion fails
_FALLBACK_QASM = (
    "OPENQASM 3.0;\n"
    "qubit[2] q;\n"
    "bit[2] c;\n"
    "h q[0];\n"
    "cx q[0], q[1];\n"
    "c[0] = measure q[0];\n"
    "c[1] = measure q[1];\n"
)


def load_fixtures(path: Path = FIXTURES_PATH) -> list[dict]:
    """Load and return the JSON fixture list."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def convert_circuit(
    code: str,
    framework: str,
    *,
    headers: dict | None = None,
    base_url: str = BASE_URL,
) -> dict:
    """
    POST to /api/converter/convert and return a result dict:
      { success, qasm, latency_ms, status_code, error }
    """
    t0 = time.perf_counter()
    try:
        resp = httpx.post(
            f"{base_url}/api/converter/convert",
            json={"code": code, "framework": framework},
            headers=headers or {},
            timeout=DEFAULT_TIMEOUT,
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        if resp.status_code == 200:
            data = resp.json()
            qasm = data.get("qasm_code") or data.get("qasm") or data.get("output") or ""
            success = bool(qasm and "OPENQASM" in qasm)
            return {
                "success": success,
                "qasm": qasm,
                "latency_ms": latency_ms,
                "status_code": resp.status_code,
                "error": None if success else f"No QASM in response: {resp.text[:200]}",
            }
        else:
            return {
                "success": False,
                "qasm": None,
                "latency_ms": latency_ms,
                "status_code": resp.status_code,
                "error": resp.text[:300],
            }
    except Exception as exc:
        return {
            "success": False,
            "qasm": None,
            "latency_ms": (time.perf_counter() - t0) * 1000,
            "status_code": -1,
            "error": str(exc),
        }


def simulate_qasm(
    qasm: str,
    *,
    backend: str = "statevector",
    shots: int = 256,
    headers: dict | None = None,
    base_url: str = BASE_URL,
) -> dict:
    """
    POST to /api/simulator/simulate and return a result dict:
      { success, latency_ms, status_code, counts, error }
    """
    t0 = time.perf_counter()
    try:
        resp = httpx.post(
            f"{base_url}/api/simulator/simulate",
            json={"qasm_code": qasm, "backend": backend, "shots": shots},
            headers=headers or {},
            timeout=DEFAULT_TIMEOUT,
        )
        latency_ms = (time.perf_counter() - t0) * 1000
        if resp.status_code == 200:
            data = resp.json()
            counts = (
                data.get("counts")
                or data.get("results", {}).get("counts")
                or {}
            )
            return {
                "success": True,
                "latency_ms": latency_ms,
                "status_code": resp.status_code,
                "counts": counts,
                "error": None,
            }
        else:
            return {
                "success": False,
                "latency_ms": latency_ms,
                "status_code": resp.status_code,
                "counts": {},
                "error": resp.text[:300],
            }
    except Exception as exc:
        return {
            "success": False,
            "latency_ms": (time.perf_counter() - t0) * 1000,
            "status_code": -1,
            "counts": {},
            "error": str(exc),
        }


def run_full_pipeline(
    example: dict,
    *,
    headers: dict | None = None,
    simulate: bool = True,
    sim_backend: str = "statevector",
    sim_shots: int = 256,
    base_url: str = BASE_URL,
) -> dict:
    """
    Run a single example through convert → simulate and return a combined result.
    """
    conv = convert_circuit(
        example["code"],
        example["framework"],
        headers=headers,
        base_url=base_url,
    )

    result = {
        "id": example["id"],
        "name": example["name"],
        "framework": example["framework"],
        "category": example["category"],
        "convert_success": conv["success"],
        "convert_latency_ms": conv["latency_ms"],
        "convert_error": conv["error"],
        "simulate_success": None,
        "simulate_latency_ms": None,
        "simulate_error": None,
        "e2e_success": False,
    }

    if simulate:
        qasm_to_use = conv["qasm"] if conv["success"] else None
        if qasm_to_use:
            sim = simulate_qasm(
                qasm_to_use,
                backend=sim_backend,
                shots=sim_shots,
                headers=headers,
                base_url=base_url,
            )
            result["simulate_success"] = sim["success"]
            result["simulate_latency_ms"] = sim["latency_ms"]
            result["simulate_error"] = sim["error"]
            result["e2e_success"] = conv["success"] and sim["success"]
        else:
            result["simulate_success"] = False
            result["simulate_latency_ms"] = 0
            result["simulate_error"] = "Skipped — conversion failed"

    return result


def run_all_examples(
    *,
    headers: dict | None = None,
    simulate: bool = True,
    sim_backend: str = "statevector",
    sim_shots: int = 256,
    base_url: str = BASE_URL,
    verbose: bool = True,
) -> list[dict]:
    """
    Load all fixtures and run the full pipeline for each example.
    Returns a list of result dicts, one per example.
    """
    examples = load_fixtures()
    results = []
    for i, ex in enumerate(examples, 1):
        if verbose:
            print(f"[{i:2d}/{len(examples)}] {ex['framework']:10s} {ex['name']}", end=" ... ")
        r = run_full_pipeline(
            ex,
            headers=headers,
            simulate=simulate,
            sim_backend=sim_backend,
            sim_shots=sim_shots,
            base_url=base_url,
        )
        results.append(r)
        if verbose:
            status = "✓" if r["e2e_success"] else ("C✓ S✗" if r["convert_success"] else "✗")
            print(f"[{status}] convert={r['convert_latency_ms']:.0f}ms")
    return results
