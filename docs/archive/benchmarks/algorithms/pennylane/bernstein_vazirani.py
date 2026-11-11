"""
PennyLane Implementation: Bernstein–Vazirani Algorithm (variable: 3–8 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: Bernstein–Vazirani
Category: Oracle-Based
Qubit Range: 3–8 (n input wires + 1 ancilla wire)
Framework: PennyLane (idiomatic style)

Uses the same SECRET_STRINGS as Qiskit and Cirq versions.

Called by: benchmarks/scripts/compile_all.py  (n ∈ 3..8)
"""

import pennylane as qml

SECRET_STRINGS = {
    3: "101",
    4: "1011",
    5: "10110",
    6: "101101",
    7: "1011010",
    8: "10110101",
}


def get_circuit(n: int = 3):
    """
    Create PennyLane BV QNode for n input qubits.

    Args:
        n: Number of input qubits (3–8).

    Returns:
        callable: PennyLane QNode.
    """
    if n not in SECRET_STRINGS:
        raise ValueError(f"n must be in {sorted(SECRET_STRINGS.keys())}")

    s     = SECRET_STRINGS[n]
    total = n + 1
    dev   = qml.device('default.qubit', wires=total)

    @qml.qnode(dev)
    def bv_circuit():
        qml.PauliX(wires=n)
        for w in range(total):
            qml.Hadamard(wires=w)
        for i, bit in enumerate(s):
            if bit == '1':
                qml.CNOT(wires=[i, n])
        for w in range(n):
            qml.Hadamard(wires=w)
        return qml.probs(wires=list(range(n)))

    return bv_circuit


if __name__ == '__main__':
    for n in [3, 4, 5]:
        qnode = get_circuit(n)
        print(f"\nBV (n={n}, secret='{SECRET_STRINGS[n]}'):")
        print(qml.draw(qnode)())
