"""
PennyLane Implementation: Deutsch–Jozsa Algorithm (variable: 3–8 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: Deutsch–Jozsa
Category: Oracle-Based
Qubit Range: 3–8 (n input wires + 1 ancilla wire)
Framework: PennyLane (idiomatic style)

Called by: benchmarks/scripts/compile_all.py  (n ∈ 3..8)
"""

import pennylane as qml


def get_circuit(n: int = 3, oracle_type: str = 'balanced'):
    """
    Create and return a PennyLane QNode for Deutsch–Jozsa.

    Args:
        n: Number of input qubits (3–8).
        oracle_type: 'balanced', 'constant_0', 'constant_1'.

    Returns:
        callable: PennyLane QNode.
    """
    total = n + 1   # n input + 1 ancilla
    dev = qml.device('default.qubit', wires=total)

    @qml.qnode(dev)
    def dj_circuit():
        # Ancilla to |−⟩
        qml.PauliX(wires=n)
        for w in range(total):
            qml.Hadamard(wires=w)

        # Oracle
        if oracle_type == 'balanced':
            for w in range(n):
                qml.CNOT(wires=[w, n])
        elif oracle_type == 'constant_1':
            qml.PauliX(wires=n)

        # H on input wires
        for w in range(n):
            qml.Hadamard(wires=w)

        return qml.probs(wires=list(range(n)))

    return dj_circuit


if __name__ == '__main__':
    for n in [3, 4, 5]:
        qnode = get_circuit(n)
        print(f"\nDJ balanced (n={n}):")
        print(qml.draw(qnode)())
