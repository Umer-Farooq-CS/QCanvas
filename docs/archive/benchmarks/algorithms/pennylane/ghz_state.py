"""
PennyLane Implementation: GHZ State (variable: 3–8 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: GHZ State
Category: Foundational
Qubit Range: 3–8
Framework: PennyLane (idiomatic style)

Called by: benchmarks/scripts/compile_all.py  (n ∈ 3..8)
"""

import pennylane as qml


def get_circuit(n: int = 3):
    """
    Create and return a PennyLane QNode for the n-qubit GHZ state.

    Args:
        n: Number of qubits (3–8).

    Returns:
        callable: PennyLane QNode that returns probabilities.
    """
    dev = qml.device('default.qubit', wires=n)

    @qml.qnode(dev)
    def ghz_circuit():
        qml.Hadamard(wires=0)
        for i in range(n - 1):
            qml.CNOT(wires=[i, i + 1])
        return qml.probs(wires=list(range(n)))

    return ghz_circuit


if __name__ == '__main__':
    for n in [3, 4, 5]:
        qnode = get_circuit(n)
        print(f"\nGHZ state ({n} qubits):")
        print(qml.draw(qnode)())
        print("Probs:", qnode())
