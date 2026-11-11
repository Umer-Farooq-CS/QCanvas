"""
PennyLane Implementation: QRNG (variable: 4–8 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: QRNG
Category: Randomness
Qubit Range: 4–8
Framework: PennyLane (idiomatic style)

Called by: benchmarks/scripts/compile_all.py  (n ∈ 4..8)
"""

import pennylane as qml


def get_circuit(n: int = 4):
    """Create and return a PennyLane QRNG QNode for n qubits."""
    dev = qml.device('default.qubit', wires=n)

    @qml.qnode(dev)
    def qrng_circuit():
        for w in range(n):
            qml.Hadamard(wires=w)
        return qml.probs(wires=list(range(n)))

    return qrng_circuit


if __name__ == '__main__':
    for n in [4, 5, 6]:
        qnode = get_circuit(n)
        print(f"\nQRNG ({n} qubits):")
        print(qml.draw(qnode)())
