"""
PennyLane Implementation: VQE – Variational Quantum Eigensolver (variable: 2–6 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: VQE (hardware-efficient ansatz, p=1)
Category: Variational
Qubit Range: 2–6
Framework: PennyLane (idiomatic style)

PennyLane idiomatic: uses qml.templates or bare gates, @qml.qnode decorator.

Called by: benchmarks/scripts/compile_all.py  (n ∈ 2..6)
"""

import numpy as np
import pennylane as qml


def get_circuit(n: int = 2):
    """Create PennyLane VQE ansatz QNode for n qubits."""
    dev   = qml.device('default.qubit', wires=n)
    theta = [np.pi / 4] * n

    @qml.qnode(dev)
    def vqe_circuit():
        # Ry rotation layer
        for w in range(n):
            qml.RY(theta[w], wires=w)
        # CNOT entanglement chain
        for w in range(n - 1):
            qml.CNOT(wires=[w, w + 1])
        return qml.probs(wires=list(range(n)))

    return vqe_circuit


if __name__ == '__main__':
    for n in [2, 3, 4]:
        qnode = get_circuit(n)
        print(f"\nVQE ansatz ({n} qubits):")
        print(qml.draw(qnode)())
