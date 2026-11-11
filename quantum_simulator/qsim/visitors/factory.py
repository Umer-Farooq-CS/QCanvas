from typing import Dict
from .base_visitor import BaseVisitor
from .cirq_visitor import CirqVisitor
from .qiskit_visitor import QiskitVisitor
from .pennylane_visitor import PennylaneVisitor
from qsim.core.exceptions import UnsupportedBackend

VISITORS: Dict[str, type[BaseVisitor]] = {
    'cirq': CirqVisitor,
    'qiskit': QiskitVisitor,
    'pennylane': PennylaneVisitor,
}


def get_visitor(name: str) -> BaseVisitor:
    """Return a visitor instance; unknown names are an error (never a silent default)."""
    key = (name or '').strip().lower()
    cls = VISITORS.get(key)
    if cls is None:
        raise UnsupportedBackend(
            f"Unknown simulation backend '{name}'. Supported backends: {', '.join(sorted(VISITORS))}."
        )
    return cls()
