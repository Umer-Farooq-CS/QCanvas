"""
PennyLane Implementation: Bit-Flip Error Correction Code (3 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: 3-Qubit Bit-Flip Code
Category: Error Correction
Qubit Range: 3
Framework: PennyLane (idiomatic style)

Called by: benchmarks/scripts/compile_all.py
"""

import pennylane as qml

dev = qml.device('default.qubit', wires=3)


@qml.qnode(dev)
def bit_flip_circuit():
    """3-qubit bit-flip error correction QNode."""
    # Prepare |+⟩
    qml.Hadamard(wires=0)

    # Encoding
    qml.CNOT(wires=[0, 1])
    qml.CNOT(wires=[0, 2])

    # Simulated error: bit-flip on wire 0
    qml.PauliX(wires=0)

    # Majority-vote correction via Toffoli
    qml.Toffoli(wires=[1, 2, 0])

    # Decoding
    qml.CNOT(wires=[0, 1])
    qml.CNOT(wires=[0, 2])

    return qml.probs(wires=[0, 1, 2])


def get_circuit():
    """Return the bit-flip QNode for use by compile_all.py."""
    return bit_flip_circuit


if __name__ == '__main__':
    probs = bit_flip_circuit()
    print("Bit-Flip Code probabilities:", probs)
    print(qml.draw(bit_flip_circuit)())
