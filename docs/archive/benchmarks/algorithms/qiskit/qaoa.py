"""
Qiskit Implementation: QAOA (variable: 2–6 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: QAOA – Quantum Approximate Optimisation Algorithm (p=1)
Category: Variational
Qubit Range: 2–6
Framework: Qiskit (idiomatic style)

Problem: Max-Cut on a ring graph (nearest-neighbour edges).
  - Cost Hamiltonian: H_C = Σ_{<i,j>} (1 - Z_i Z_j) / 2
  - Mixer Hamiltonian: H_B = Σ_i X_i
  - p=1 layer (one cost + one mixer)
  - Parameter values fixed: γ=π/4, β=π/8 for structural benchmarking

Cost unitary: Rzz(2γ) on each edge = CX + Rz(2γ) + CX
Mixer unitary: Rx(2β) on each qubit

Called by:
  - benchmarks/scripts/compile_all.py  (n ∈ 2..6)
  - benchmarks/notebooks/nb03_statistical_analysis.ipynb
"""

import numpy as np
from qiskit import QuantumCircuit


def get_circuit(n: int = 2):
    """
    Build the QAOA p=1 circuit for Max-Cut on a ring graph with n nodes.

    Args:
        n: Number of qubits (graph nodes) — 2 to 6.

    Returns:
        QuantumCircuit: QAOA circuit with parameters bound to γ=π/4, β=π/8.
    """
    if n < 2:
        raise ValueError(f"QAOA requires n >= 2 qubits, got {n}")

    gamma = np.pi / 4   # cost layer parameter
    beta  = np.pi / 8   # mixer layer parameter

    # Ring graph edges for Max-Cut
    edges = [(i, (i + 1) % n) for i in range(n)]

    qc = QuantumCircuit(n, n)

    # Initial state: equal superposition
    qc.h(range(n))

    # Cost unitary: Rzz(2γ) on each edge (ring topology)
    # Rzz(θ) = CX · Rz(θ) · CX
    for u, v in edges:
        qc.cx(u, v)
        qc.rz(2 * gamma, v)
        qc.cx(u, v)

    # Mixer unitary: Rx(2β) on each qubit
    for i in range(n):
        qc.rx(2 * beta, i)

    qc.measure(range(n), range(n))
    return qc


if __name__ == '__main__':
    for n in [2, 3, 4]:
        qc = get_circuit(n)
        print(f"\nQAOA p=1 Max-Cut ring (n={n}):")
        print(qc.draw('text'))
        print(f"  Gate count: {qc.count_ops()}")
