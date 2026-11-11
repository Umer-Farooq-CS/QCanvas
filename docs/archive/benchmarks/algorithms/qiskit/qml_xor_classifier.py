"""
Qiskit Implementation: QML XOR Classifier (variable: 2–4 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: QML XOR Classifier (angle-encoding + variational layer)
Category: Quantum Machine Learning
Qubit Range: 2–4
Framework: Qiskit (idiomatic style)

Structure:
  - Angle encoding: Ry(x_i * π) for each input feature into each qubit
  - Variational layer: Rz(θ_i) per qubit + CX chain
  - Measurement of qubit 0 (classifier output)

Input: Fixed data point x = [0.5, 0.3, 0.7, 0.2, ...] (first n values)
Weights: θ_i = π/4 for all i (structural benchmarking — no training)

Goal: Benchmark parametric circuit compilation, NOT actual classification.
The XOR pattern is a standard non-linearly-separable benchmark in QML.

Called by:
  - benchmarks/scripts/compile_all.py  (n ∈ 2..4)
  - benchmarks/notebooks/nb03_statistical_analysis.ipynb
"""

import numpy as np
from qiskit import QuantumCircuit


# Fixed input data point (first n values used per qubit count)
DATA_POINT = [0.5, 0.3, 0.7, 0.2]


def get_circuit(n: int = 2):
    """
    Build the n-qubit QML XOR circuit.

    Args:
        n: Number of qubits (2–4).

    Returns:
        QuantumCircuit: Angle-encoded variational classifier circuit.
    """
    if n < 2 or n > 4:
        raise ValueError(f"QML XOR classifier uses 2–4 qubits, got {n}")

    x = DATA_POINT[:n]   # Input features for this qubit count
    theta = [np.pi / 4] * n   # Fixed variational parameters

    qc = QuantumCircuit(n, 1)

    # Angle encoding layer
    for i in range(n):
        qc.ry(x[i] * np.pi, i)

    # Entanglement layer (CX chain)
    for i in range(n - 1):
        qc.cx(i, i + 1)

    # Variational layer: Rz(θ_i) on each qubit
    for i in range(n):
        qc.rz(theta[i], i)

    # Measure qubit 0 as classifier output
    qc.measure(0, 0)

    return qc


if __name__ == '__main__':
    for n in [2, 3, 4]:
        qc = get_circuit(n)
        print(f"\nQML XOR Classifier (n={n}):")
        print(qc.draw('text'))
        print(f"  Gate count: {qc.count_ops()}")
