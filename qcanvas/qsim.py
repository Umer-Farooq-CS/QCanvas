"""
QSim wrapper module for hybrid execution.

This module provides a clean interface to QSim that can be imported
in user code as `import qsim`.

Usage:
    import qsim
    result = qsim.run(qasm_code, shots=1024, backend="cirq")
    print(result.counts)
"""

import sys
import os
from typing import Optional, Dict, Any

# Add project root to path for imports
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from .result import SimulationResult

# Import actual QSim
try:
    from qsim import run_qasm as _qsim_run, RunArgs as _RunArgs, SimResult as _SimResult
    QSIM_AVAILABLE = True
except ImportError as e:
    QSIM_AVAILABLE = False
    _qsim_run = None
    _RunArgs = None
    _SimResult = None


# Track simulation runs for result collection
_simulation_results: list = []


# ---------------------------------------------------------------------------
# FastQSim online-mode resolution (cached)
# ---------------------------------------------------------------------------
# Previously every qsim.run() created a boto3 client and called AWS SSM, which
# added ~1-2 s per call (credential discovery + network) and failed noisily
# outside AWS.  The decision is now cached per process for
# FASTQSIM_ONLINE_MODE_CACHE_SECONDS (default 30, same knob as
# SimulationService).  The API process resolves it once and passes the answer
# to each isolated hybrid run via set_online_mode_override(), so the short-lived
# child processes never talk to SSM themselves.
import threading as _threading
import time as _time

_online_mode_lock = _threading.Lock()
_online_mode_cache: Optional[tuple] = None  # (value, expires_at_monotonic)
_online_mode_override: Optional[bool] = None


def _online_mode_ttl() -> float:
    try:
        return max(0.0, float(os.getenv("FASTQSIM_ONLINE_MODE_CACHE_SECONDS", "30")))
    except ValueError:
        return 30.0


def _lookup_online_mode_ssm() -> bool:
    ssm_param = os.getenv("SSM_FASTQSIM_ONLINE_MODE_PARAM", "/qcanvas/production/fastqsim_online_mode")
    try:
        import boto3
        config = boto3.session.Config(connect_timeout=1, read_timeout=1, retries={'max_attempts': 1})
        ssm = boto3.client('ssm', config=config)
        resp = ssm.get_parameter(Name=ssm_param, WithDecryption=False)
        return resp['Parameter']['Value'].strip().lower() in ("true", "1", "yes")
    except Exception:
        return False


def set_online_mode_override(value: Optional[bool]) -> None:
    """Force online mode on/off for this process (None = resolve normally)."""
    global _online_mode_override
    _online_mode_override = value


def resolve_online_mode(force_refresh: bool = False) -> bool:
    """Should qsim.run() forward to FastQSim cloud?

    Order: explicit override -> FASTQSIM_ONLINE_MODE env var (any non-empty
    value short-circuits, like SimulationService) -> cached SSM lookup.
    """
    if _online_mode_override is not None:
        return _online_mode_override

    val = os.getenv("FASTQSIM_ONLINE_MODE")
    if val:
        return val.strip().lower() in ("true", "1", "yes")

    global _online_mode_cache
    ttl = _online_mode_ttl()
    with _online_mode_lock:
        now = _time.monotonic()
        if not force_refresh and ttl > 0 and _online_mode_cache is not None and _online_mode_cache[1] > now:
            return _online_mode_cache[0]
        value = _lookup_online_mode_ssm()
        if ttl > 0:
            _online_mode_cache = (value, _time.monotonic() + ttl)
        return value


def get_simulation_results() -> list:
    """Get all simulation results from this execution."""
    return _simulation_results.copy()


def clear_simulation_results() -> None:
    """Clear stored simulation results."""
    global _simulation_results
    _simulation_results = []


def run(
    qasm_code: str,
    shots: int = 1024,
    backend: str = "cirq"
) -> SimulationResult:
    """
    Execute OpenQASM 3.0 code using QSim.
    
    Args:
        qasm_code: OpenQASM 3.0 code to execute
        shots: Number of measurement shots (default: 1024)
        backend: Simulation backend to use (default: "cirq")
            Options: "cirq", "qiskit", "pennylane"
    
    Returns:
        SimulationResult with counts, probabilities, and metadata
        
    Raises:
        RuntimeError: If QSim is not available or execution fails
        
    Example:
        >>> qasm = '''
        ... OPENQASM 3.0;
        ... include "stdgates.inc";
        ... qubit[2] q;
        ... h q[0];
        ... cx q[0], q[1];
        ... bit[2] c;
        ... c = measure q;
        ... '''
        >>> result = qsim.run(qasm, shots=1000, backend="cirq")
        >>> print(result.counts)
        {'00': 498, '11': 502}
    """
    global _simulation_results
    
    if not QSIM_AVAILABLE:
        raise RuntimeError(
            "QSim is not available. Please ensure qsim package is installed."
        )
    
    # Validate backend
    valid_backends = ['cirq', 'qiskit', 'pennylane']
    if backend not in valid_backends:
        raise ValueError(
            f"Invalid backend: '{backend}'. "
            f"Valid options: {', '.join(valid_backends)}"
        )
    
    # Validate shots
    if shots < 0:
        raise ValueError(f"Shots must be non-negative, got: {shots}")
    
    try:
        # Check if online mode is enabled for cloud forwarding (cached)
        try:
            online_mode = resolve_online_mode()
        except Exception:
            online_mode = False

        if online_mode:
            print(f"🚀 [QSim Wrapper] Forwarding simulation to FastQSim Online Cloud on backend '{backend}'...")
            import fastqsim
            client = fastqsim.init()
            job = client.run(circuit=qasm_code, backend=backend, shots=shots, asynchronous=False)
            res = job.result()
            
            counts = res.counts if hasattr(res, 'counts') else {}
            probs = res.probs if hasattr(res, 'probs') else {}
            statevector = res.statevector if hasattr(res, 'statevector') else None
            exec_time_sec = getattr(job, 'execution_time_seconds', getattr(res, 'execution_time_seconds', 0.0))
            cpu_time_sec = getattr(job, 'cpu_seconds_total', 0.0)
            peak_ram_mb = getattr(job, 'peak_memory_mb', 0.0)
            billing_cpu = getattr(job, 'billing_cpu_millicore_seconds', 0.0)
            billing_mem = getattr(job, 'billing_memory_gb_seconds', 0.0)
            tags = getattr(job, 'tags', {})
            job_metadata = getattr(job, 'metadata', {})
            
            def _iso(val):
                return val.isoformat() if hasattr(val, 'isoformat') else None
            
            total_counts = sum(counts.values()) if counts else 0
            probabilities = {}
            if total_counts > 0:
                for state, count in counts.items():
                    probabilities[state] = count / total_counts
            elif probs:
                probabilities = dict(probs)
                
            exec_time_str = f"{exec_time_sec * 1000:.2f}ms" if exec_time_sec > 0 else "10.00ms"
            cpu_pct = min((cpu_time_sec / exec_time_sec) * 100.0, 100.0) if exec_time_sec > 0 and cpu_time_sec > 0 else 0.0
            cpu_usage_str = f"{cpu_pct:.1f}%"
            memory_usage_str = f"{peak_ram_mb:.1f}MB" if peak_ram_mb > 0 else "0.10MB"
            
            result = SimulationResult(
                counts=dict(counts) if counts else {},
                probabilities=probabilities,
                statevector=statevector,
                shots=shots,
                backend=backend,
                execution_time=exec_time_str,
                simulation_time=exec_time_str,
                memory_usage=memory_usage_str,
                cpu_usage=cpu_usage_str,
                fidelity=100.0,
                n_qubits=len(next(iter(counts.keys()))) if counts else 0,
                metadata={
                    "backend": backend,
                    "shots": shots,
                    "job_id": getattr(job, 'job_id', None),
                    "online": True,
                    "successful_shots": total_counts,
                    "execution_time_seconds": exec_time_sec,
                    "cpu_seconds_total": cpu_time_sec,
                    "peak_memory_mb": peak_ram_mb,
                    "billing_cpu_millicore_seconds": billing_cpu,
                    "billing_memory_gb_seconds": billing_mem,
                    "tags": tags,
                    "metadata": job_metadata,
                    "queue_enqueued_at": _iso(getattr(job, 'queue_enqueued_at', None)),
                    "execution_started_at": _iso(getattr(job, 'execution_started_at', None)),
                    "execution_finished_at": _iso(getattr(job, 'execution_finished_at', None)),
                    "completed_at": _iso(getattr(job, 'completed_at', None)),
                    "execution_time": exec_time_str,
                    "simulation_time": exec_time_str,
                    "memory_usage": memory_usage_str,
                    "cpu_usage": cpu_usage_str,
                },
            )
            _simulation_results.append(result.to_dict())
            return result

        # Fallback to local QSim execution
        # Create run arguments
        args = _RunArgs(
            qasm_input=qasm_code,
            backend=backend,
            shots=shots
        )
        
        # Execute with QSim
        sim_result: _SimResult = _qsim_run(args)
        
        # Convert to our SimulationResult format
        metadata = sim_result.metadata or {}
        
        # Calculate probabilities from counts
        total_counts = sum(sim_result.counts.values()) if sim_result.counts else 0
        probabilities = {}
        if total_counts > 0:
            for state, count in sim_result.counts.items():
                probabilities[state] = count / total_counts
        elif sim_result.probs:
            probabilities = dict(sim_result.probs)
        
        result = SimulationResult(
            counts=dict(sim_result.counts) if sim_result.counts else {},
            probabilities=probabilities,
            statevector=None,  # Not always available
            shots=shots,
            backend=backend,
            execution_time=metadata.get('execution_time', ''),
            simulation_time=metadata.get('simulation_time', ''),
            memory_usage=metadata.get('memory_usage', ''),
            cpu_usage=metadata.get('cpu_usage', ''),
            fidelity=metadata.get('fidelity', 100.0),
            n_qubits=metadata.get('n_qubits', 0),
            metadata=metadata,
        )
        
        # Store result for collection
        _simulation_results.append(result.to_dict())
        
        return result
        
    except Exception as e:
        raise RuntimeError(f"QSim execution failed: {str(e)}") from e


def run_batch(
    qasm_codes: list,
    shots: int = 1024,
    backend: str = "cirq"
) -> list:
    """
    Execute multiple QASM codes in batch.
    
    Args:
        qasm_codes: List of OpenQASM 3.0 code strings
        shots: Number of measurement shots (default: 1024)
        backend: Simulation backend to use (default: "cirq")
    
    Returns:
        List of SimulationResult objects
    """
    results = []
    for qasm in qasm_codes:
        result = run(qasm, shots=shots, backend=backend)
        results.append(result)
    return results


# Aliases for convenience
execute = run
simulate = run
