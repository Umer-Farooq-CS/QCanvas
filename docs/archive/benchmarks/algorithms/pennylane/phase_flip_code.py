"""
PennyLane Implementation: Phase-Flip Error Correction Code (3 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: 3-Qubit Phase-Flip Code
Category: Error Correction
Qubit Range: 3
Framework: PennyLane (idiomatic style)

Called by: benchmarks/scripts/compile_all.py
"""

import pennylane as qml

dev = qml.device('default.qubit', wires=3)


@qml.qnode(dev)
def phase_flip_circuit():
    """3-qubit phase-flip error correction QNode."""
    # Prepare |+⟩ on data wire
    qml.Hadamard(wires=0)

    # Encoding (H-basis bit-flip code)
    qml.CNOT(wires=[0, 1])
    qml.CNOT(wires=[0, 2])
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    qml.Hadamard(wires=2)

    # Simulated phase-flip error: Z on wire 0
    qml.PauliZ(wires=0)

    # Decoding
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    qml.Hadamard(wires=2)
    qml.Toffoli(wires=[1, 2, 0])
    qml.CNOT(wires=[0, 1])
    qml.CNOT(wires=[0, 2])

    return qml.probs(wires=[0, 1, 2])


def get_circuit():
    """Return the phase-flip QNode for use by compile_all.py."""
    return phase_flip_circuit


if __name__ == '__main__':
    probs = phase_flip_circuit()
    print("Phase-Flip Code probabilities:", probs)
    print(qml.draw(phase_flip_circuit)())
