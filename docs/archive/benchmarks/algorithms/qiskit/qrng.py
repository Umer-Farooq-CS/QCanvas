"""
Qiskit Implementation: Quantum Random Number Generator (variable: 4–8 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: QRNG (Quantum Random Number Generator)
Category: Randomness
Qubit Range: 4–8
Framework: Qiskit (idiomatic style)

Pure Hadamard baseline — applies H to every qubit then measures.
The simplest non-trivial circuit that isolates gate-translation overhead
(no 2-qubit gates, no oracle). Any gate-count difference across frameworks
indicates compiler overhead, not algorithmic complexity.

Expected output: Uniform distribution over all 2^n basis states.

Called by:
  - benchmarks/scripts/compile_all.py  (n ∈ 4..8)
  - benchmarks/notebooks/nb03_statistical_analysis.ipynb
"""

from qiskit import QuantumCircuit


def get_circuit(n: int = 4):
    """
    Build the n-qubit QRNG circuit.

    Args:
        n: Number of qubits (4–8).

    Returns:
        QuantumCircuit: n-qubit all-Hadamard circuit.
    """
    qc = QuantumCircuit(n, n)
    qc.h(range(n))
    qc.measure(range(n), range(n))
    return qc


if __name__ == '__main__':
    for n in [4, 5, 6]:
        qc = get_circuit(n)
        print(f"\nQRNG ({n} qubits): {qc.count_ops()}")
        print(qc.draw('text'))
