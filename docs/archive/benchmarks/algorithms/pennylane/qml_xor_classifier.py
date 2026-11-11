"""
PennyLane Implementation: QML XOR Classifier (variable: 2–4 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: QML XOR Classifier (angle encoding + variational layer)
Category: Quantum Machine Learning
Qubit Range: 2–4
Framework: PennyLane (idiomatic style)

Called by: benchmarks/scripts/compile_all.py  (n ∈ 2..4)
"""

import numpy as np
import pennylane as qml

DATA_POINT = [0.5, 0.3, 0.7, 0.2]


def get_circuit(n: int = 2):
    """Create PennyLane QML XOR classifier QNode for n qubits."""
    dev   = qml.device('default.qubit', wires=n)
    x     = DATA_POINT[:n]
    theta = [np.pi / 4] * n

    @qml.qnode(dev)
    def classifier_circuit():
        # Angle encoding
        for w in range(n):
            qml.RY(x[w] * np.pi, wires=w)
        # Entanglement
        for w in range(n - 1):
            qml.CNOT(wires=[w, w + 1])
        # Variational Rz layer
        for w in range(n):
            qml.RZ(theta[w], wires=w)
        # Output: expectation on wire 0
        return qml.probs(wires=[0])

    return classifier_circuit


if __name__ == '__main__':
    for n in [2, 3, 4]:
        qnode = get_circuit(n)
        print(f"\nQML XOR Classifier ({n} qubits):")
        print(qml.draw(qnode)())
