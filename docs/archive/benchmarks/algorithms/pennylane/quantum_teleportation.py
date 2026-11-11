"""
PennyLane Implementation: Quantum Teleportation (3 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: Quantum Teleportation
Category: Quantum Communication
Qubit Range: 3
Framework: PennyLane (idiomatic style)

PennyLane note: Mid-circuit measurements and conditional operations use
qml.measure() and qml.cond() (available in PennyLane ≥ 0.38). This differs
structurally from both Qiskit (c_if) and Cirq (ClassicallyControlledOperation),
producing a different QASM AST structure.

Called by: benchmarks/scripts/compile_all.py
"""

import pennylane as qml

dev = qml.device('default.qubit', wires=3)


@qml.qnode(dev)
def teleportation_circuit():
    """
    3-qubit quantum teleportation QNode.

    Wire assignment:
      wire 0 = qubit to teleport (initialised to |+⟩)
      wire 1 = Alice's entangled qubit
      wire 2 = Bob's entangled qubit

    Returns:
        np.ndarray: Probabilities of Bob's qubit.
    """
    # Prepare state to teleport: |+⟩
    qml.Hadamard(wires=0)

    # Create Bell pair between Alice (wire 1) and Bob (wire 2)
    qml.Hadamard(wires=1)
    qml.CNOT(wires=[1, 2])

    # Alice's Bell measurement operations
    qml.CNOT(wires=[0, 1])
    qml.Hadamard(wires=0)

    # Mid-circuit measurements
    m0 = qml.measure(0)
    m1 = qml.measure(1)

    # Bob's conditional corrections
    qml.cond(m1, qml.PauliX)(wires=2)
    qml.cond(m0, qml.PauliZ)(wires=2)

    return qml.probs(wires=[2])


def get_circuit():
    """Return the teleportation QNode for use by compile_all.py."""
    return teleportation_circuit


if __name__ == '__main__':
    probs = teleportation_circuit()
    print("Bob's qubit probabilities:", probs)
    print(qml.draw(teleportation_circuit)())
