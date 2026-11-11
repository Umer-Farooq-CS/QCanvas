"""
PennyLane Implementation: QAOA (variable: 2–6 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: QAOA – Quantum Approximate Optimisation Algorithm (p=1)
Category: Variational
Qubit Range: 2–6
Framework: PennyLane (idiomatic style)

PennyLane idiomatic: uses qml.IsingZZ for the cost Hamiltonian terms.

Called by: benchmarks/scripts/compile_all.py  (n ∈ 2..6)
"""

import numpy as np
import pennylane as qml


def get_circuit(n: int = 2):
    """Create PennyLane QAOA p=1 QNode for Max-Cut on ring graph."""
    dev   = qml.device('default.qubit', wires=n)
    gamma = np.pi / 4
    beta  = np.pi / 8
    edges = [(i, (i + 1) % n) for i in range(n)]

    @qml.qnode(dev)
    def qaoa_circuit():
        # Initial superposition
        for w in range(n):
            qml.Hadamard(wires=w)

        # Cost unitary: IsingZZ(2γ) on each edge
        for u, v in edges:
            qml.IsingZZ(2 * gamma, wires=[u, v])

        # Mixer unitary: RX(2β) on each qubit
        for w in range(n):
            qml.RX(2 * beta, wires=w)

        return qml.probs(wires=list(range(n)))

    return qaoa_circuit


if __name__ == '__main__':
    for n in [2, 3, 4]:
        qnode = get_circuit(n)
        print(f"\nQAOA p=1 ring (n={n}):")
        print(qml.draw(qnode)())
