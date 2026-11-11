from typing import Dict
from .base import BaseBackend
from .cirq import CirqBackend
from .qiskit import QiskitBackend
from .pennylane import PennylaneBackend
from qsim.core.exceptions import UnsupportedBackend

BACKENDS: Dict[str, type[BaseBackend]] = {
    'cirq': CirqBackend,
    'qiskit': QiskitBackend,
    'pennylane': PennylaneBackend,
}


def get_backend(name: str) -> BaseBackend:
    """Return a backend instance; unknown names are an error (never a silent default)."""
    key = (name or '').strip().lower()
    cls = BACKENDS.get(key)
    if cls is None:
        raise UnsupportedBackend(
            f"Unknown simulation backend '{name}'. Supported backends: {', '.join(sorted(BACKENDS))}."
        )
    return cls()
