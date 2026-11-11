import os
from pathlib import Path
from typing import Union

from .types import RunArgs, SimResult
from .exceptions import QSimError, ParseError, UnsupportedBackend

# External module imports
from qsim.qasm_parser import parse_openqasm3  # → openqasm3.Module (AST)
from qsim.visitors.factory import get_visitor  # → BaseVisitor instance
from qsim.backends.factory import get_backend  # → BaseBackend instance

DEFAULT_MAX_QUBITS = 24


def _qubit_count(circuit, spec) -> int:
    """Qubits in the circuit actually built by the visitor (what drives memory)."""
    counts = []
    for attr in ("num_qubits", "n_qubits"):
        v = getattr(circuit, attr, None)
        if isinstance(v, int):
            counts.append(v)
    all_q = getattr(circuit, "all_qubits", None)
    if callable(all_q):
        try:
            counts.append(len(list(all_q())))
        except Exception:
            pass
    wires = getattr(circuit, "wires", None)
    if wires is not None:
        try:
            counts.append(len(wires))
        except Exception:
            pass
    if spec is not None and spec.get("qubits") is not None:
        counts.append(len(spec["qubits"]))
    return max(counts) if counts else 0


def _max_qubits(args: RunArgs) -> int:
    if getattr(args, "max_qubits", None):
        return int(args.max_qubits)
    try:
        return int(os.environ.get("QSIM_MAX_QUBITS", DEFAULT_MAX_QUBITS))
    except ValueError:
        return DEFAULT_MAX_QUBITS


def run_qasm(args: Union[RunArgs, dict]) -> SimResult:
    """
    Core orchestration: Parse QASM3 → Visit (build circuit) → Backend (simulate).

    Example:
        result = run_qasm(RunArgs(qasm_input="OPENQASM 3.0; ...", shots=100))

    Returns:
        SimResult with counts/metadata.

    Raises:
        QASMError subclasses for failures.
    """
    if isinstance(args, dict):
        args = RunArgs(**args)

    try:
        # 1. Parse QASM3 to AST
        qasm_input = args.qasm_input
        if isinstance(qasm_input, Path):
            qasm_input = qasm_input.read_text(encoding='utf-8')
        module = parse_openqasm3(qasm_input)

        # 2. Visitor: Traverse AST and build circuit
        # Resolve the backend first so an unknown name fails before any work.
        backend_name = args.backend
        backend = get_backend(backend_name)
        visitor = get_visitor(backend_name)
        visitor.visit(module)
        circuit = visitor.finalize()  # Assumes _block accumulator

        # 3. Backend: Run simulation. The visitor's output spec makes every
        #    backend report bitstrings in the same layout (see BaseBackend).
        spec = visitor.output_spec() if hasattr(visitor, 'output_spec') else None

        # Enforce the qubit cap on the circuit that was actually built (not on
        # the QASM text, which can declare sizes via expressions/consts).
        limit = _max_qubits(args)
        n_built = _qubit_count(circuit, spec)
        if n_built > limit:
            raise QSimError(
                f"Circuit uses {n_built} qubits; the limit on this server is {limit}."
            )

        raw_result = backend.run(circuit, args.shots, spec=spec, seed=getattr(args, 'seed', None))
        counts = backend.to_counts(raw_result)

        # 4. Build SimResult (infer n_qubits from circuit if possible)
        if spec is not None and spec.get('qubits') is not None:
            n_qubits = len(spec['qubits'])
        else:
            n_qubits = (
                getattr(circuit, 'n_qubits', None)
                or getattr(circuit, 'num_qubits', None)
                or len(list(getattr(circuit, 'all_qubits', lambda: [])()))
                or len(getattr(circuit, 'wires', []))  # PennyLane
                or 1  # Fallback
            )
        metadata = {
            'n_qubits': n_qubits,
            'backend': args.backend,
            'shots': args.shots,
            'success': True,
        }
        if spec is not None:
            metadata['measured'] = bool(spec.get('measured'))
            metadata['n_clbits'] = len(spec.get('clbits') or [])
        probs = raw_result.get('probs') if args.shots == 0 else None

        return SimResult(counts=counts, metadata=metadata, probs=probs)

    except Exception as e:
        # Wrap and re-raise known exceptions
        if isinstance(e, (QSimError, ParseError, UnsupportedBackend)):
            raise
        raise QSimError(f"Simulation failed: {str(e)}") from e
    