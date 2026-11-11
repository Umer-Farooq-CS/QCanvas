from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

import numpy as np


class BaseBackend(ABC):
    """
    Abstract base for QSim backends.
    Consumes visitor circuit and simulates.

    Output convention (identical for every backend):
      * If the program measures anything, each counts key has one character per
        declared classical bit, registers in declaration order and, inside a
        register, bit 0 first.  For ``bit[3] c;`` the key "100" means c[0]=1,
        c[1]=0, c[2]=0.  Bits that are never measured read as their initial value.
      * If the program measures nothing, every qubit is sampled and the key has
        one character per declared qubit (q[0] first).

    ``spec`` (built by the visitor's ``output_spec()``) carries the backend-specific
    handles needed to produce that layout.
    """

    @abstractmethod
    def run(self, circuit: Any, shots: int = 1024, spec: Optional[Dict[str, Any]] = None,
            seed: Optional[int] = None) -> Dict[str, Any]:
        """
        Run simulation.
        Args:
            circuit: From visitor.finalize() (e.g., cirq.Circuit).
            shots: >0 for sampling; 0 for exact state/probs.
            spec: Output layout from the visitor (see class docstring).
            seed: Optional RNG seed for reproducible sampling.
        Returns:
            {'counts': {'00': 512, ...}, 'probs': {...}, 'metadata': {...}}
        """
        pass

    def to_counts(self, result: Dict[str, Any]) -> Dict[str, int]:
        """Normalize to counts (default impl)."""
        return result.get('counts', {})

    @staticmethod
    def _bit_matrix_to_counts(bits: np.ndarray) -> Dict[str, int]:
        """Turn a (shots, n_bits) 0/1 matrix into a counts dict."""
        bits = np.asarray(bits, dtype=np.int64)
        if bits.ndim == 1:
            bits = bits.reshape(-1, 1)
        counts: Dict[str, int] = {}
        if bits.shape[1] == 0:
            counts[''] = int(bits.shape[0])
            return counts
        rows, freq = np.unique(bits, axis=0, return_counts=True)
        for row, n in zip(rows, freq):
            counts[''.join(str(int(b)) for b in row)] = int(n)
        return counts
