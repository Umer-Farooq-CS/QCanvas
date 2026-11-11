"""
Top-level QCanvas Python API for Hybrid CPU–QPU execution.

This module is intentionally lightweight and acts as a friendly import shim
so that user code can simply write:

    from qcanvas import compile
    import qsim

without worrying about the internal package layout.
"""

import sys
import os
from importlib import import_module
from typing import Optional

__version__ = "0.0.0"

# Primary goal: provide a lightweight `compile()` that converts framework
# circuits/objects to OpenQASM 3.0 using the `quantum_converters` package.
# Converters are imported lazily so `import qcanvas` works in a clean
# environment without requiring every optional quantum framework dependency.


def _load_converter(module_name: str, function_name: str):
    try:
        module = import_module(f"quantum_converters.converters.{module_name}")
        return getattr(module, function_name)
    except Exception:
        return None

try:
    from qcanvas_runtime.result import SimulationResult, HybridExecutionResult  # type: ignore[attr-defined]
except Exception:
    SimulationResult = None  # type: ignore[assignment]
    HybridExecutionResult = None  # type: ignore[assignment]


def _import_runtime_core():
    try:
        from qcanvas_runtime.core import compile as runtime_compile, compile_and_execute as runtime_compile_and_execute  # type: ignore[attr-defined]
        return runtime_compile, runtime_compile_and_execute
    except Exception:
        _CURRENT_FILE = os.path.abspath(__file__)
        _PROJECT_ROOT = os.path.dirname(os.path.dirname(_CURRENT_FILE))
        _BACKEND_ROOT = os.path.join(_PROJECT_ROOT, "backend")
        if os.path.isdir(_BACKEND_ROOT) and _BACKEND_ROOT not in sys.path:
            sys.path.insert(0, _BACKEND_ROOT)
            from qcanvas_runtime.core import compile as runtime_compile, compile_and_execute as runtime_compile_and_execute  # type: ignore[attr-defined]
            return runtime_compile, runtime_compile_and_execute
        raise ImportError("qcanvas_runtime is not available")


def _detect_framework(obj):
    """Very small heuristic to guess framework from object type or provided string."""
    if isinstance(obj, str):
        return "qasm"
    try:
        import cirq

        if isinstance(obj, cirq.Circuit):
            return "cirq"
    except Exception:
        pass
    try:
        import qiskit

        # Qiskit circuits are typically QuantumCircuit
        if hasattr(qiskit, "QuantumCircuit") and isinstance(obj, qiskit.QuantumCircuit):
            return "qiskit"
    except Exception:
        pass
    try:
        import pennylane as pl

        if hasattr(pl, "QNode") and isinstance(obj, pl.QNode):
            return "pennylane"
    except Exception:
        pass
    return None


def compile(obj, framework: Optional[str] = None, **kwargs) -> str:
    """Compile a framework object or source string to OpenQASM 3.0.

    - If `quantum_converters` is available, use it to perform conversion.
    - If not, fall back to the legacy `qcanvas_runtime.core.compile` if present.
    """
    if framework is None:
        framework = _detect_framework(obj)

    cirq_converter = _load_converter("cirq_to_qasm", "convert_cirq_to_qasm3") if framework == "cirq" else None
    qiskit_converter = _load_converter("qiskit_to_qasm", "convert_qiskit_to_qasm3") if framework == "qiskit" else None
    pennylane_converter = _load_converter("pennylane_to_qasm", "convert_pennylane_to_qasm3") if framework == "pennylane" else None

    if framework == "cirq" and cirq_converter is not None:
        result = cirq_converter(obj, **kwargs)
        return getattr(result, "qasm_code", result)
    if framework == "cirq" and cirq_converter is None:
        raise ImportError(
            "Cirq converter is not available in this environment. Install 'cirq>=1.0,<2' "
            "and make sure the same interpreter is running your app."
        )

    if framework == "qiskit" and qiskit_converter is not None and not isinstance(obj, str):
        # A QuantumCircuit OBJECT (e.g. `compile(qc)` in hybrid code). The
        # convenience converter expects source text, so use the converter's
        # circuit-object path; same QASM builder, same output style.
        from quantum_converters.converters.qiskit_to_qasm import QiskitToQASM3Converter

        return QiskitToQASM3Converter()._convert_to_qasm3(obj)
    if framework == "qiskit" and qiskit_converter is not None:
        result = qiskit_converter(obj, **kwargs)
        return getattr(result, "qasm_code", result)
    if framework == "qiskit" and qiskit_converter is None:
        raise ImportError(
            "Qiskit converter is not available in this environment. Install 'qiskit>=1.1,<3' "
            "and restart the backend in the same virtual environment."
        )

    if framework == "pennylane" and pennylane_converter is not None:
        result = pennylane_converter(obj, **kwargs)
        return getattr(result, "qasm_code", result)
    if framework == "pennylane" and pennylane_converter is None:
        raise ImportError(
            "PennyLane converter is not available in this environment. Install 'pennylane>=0.34,<1' "
            "and restart the backend in the same virtual environment."
        )

    if framework == "qasm" or framework is None:
        if isinstance(obj, str):
            return obj
        raise ValueError("String QASM expected when framework='qasm' or unknown object type.")

    # Fallback to runtime only for legacy callers that still rely on it.
    try:
        runtime_compile, _ = _import_runtime_core()
        return runtime_compile(obj, framework=framework, **kwargs)
    except Exception:
        pass

    raise ImportError("No converter or runtime available. Install quantum_converters or include the backend runtime.")


def compile_and_execute(*args, **kwargs):
    """Compatibility wrapper: only available when runtime is present."""
    runtime_compile, runtime_compile_and_execute = _import_runtime_core()
    return runtime_compile_and_execute(*args, **kwargs)

__all__ = [
    "compile",
    "compile_and_execute",
    "SimulationResult",
    "HybridExecutionResult",
]

__version__ = "1.0.5"
