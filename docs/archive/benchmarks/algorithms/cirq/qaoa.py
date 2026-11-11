"""
Cirq Implementation: QAOA (variable: 2–6 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: QAOA – Quantum Approximate Optimisation Algorithm (p=1)
Category: Variational
Qubit Range: 2–6
Framework: Cirq (idiomatic style)

Problem: Max-Cut on a ring graph (nearest-neighbour edges).
Cost unitary: Rzz(2γ) = CNOT · Rz(2γ) · CNOT on each edge
Mixer unitary: Rx(2β) on each qubit

Cirq uses cirq.CNOT, cirq.rz, cirq.rx native operations.
Parameters: γ = π/4, β = π/8.

Called by: benchmarks/scripts/compile_all.py  (n ∈ 2..6)
"""

import numpy as np
import cirq


def get_circuit(n: int = 2):
    """
    Build QAOA p=1 Max-Cut circuit for n nodes on a ring in Cirq.

    Args:
        n: Number of qubits (2–6).

    Returns:
        cirq.Circuit: QAOA circuit.
    """
    qubits = cirq.LineQubit.range(n)
    gamma  = np.pi / 4
    beta   = np.pi / 8

    edges = [(i, (i + 1) % n) for i in range(n)]
    ops = list(cirq.H(q) for q in qubits)

    # Cost unitary
    for u, v in edges:
        ops.append(cirq.CNOT(qubits[u], qubits[v]))
        ops.append(cirq.rz(2 * gamma)(qubits[v]))
        ops.append(cirq.CNOT(qubits[u], qubits[v]))

    # Mixer unitary
    ops.extend(cirq.rx(2 * beta)(q) for q in qubits)

    ops.append(cirq.measure(*qubits, key='result'))

    return cirq.Circuit(ops)


if __name__ == '__main__':
    for n in [2, 3, 4]:
        c = get_circuit(n)
        print(f"\nQAOA p=1 ring (n={n}):")
        print(c)
