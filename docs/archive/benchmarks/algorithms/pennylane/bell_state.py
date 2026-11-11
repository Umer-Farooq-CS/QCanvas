"""
PennyLane Implementation: Bell State (2 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: Bell State
Category: Foundational
Qubit Range: 2
Framework: PennyLane (idiomatic style — @qml.qnode decorator)

Idiomatic PennyLane conventions:
  - qml.device('default.qubit', wires=N)
  - @qml.qnode(dev) decorator on the circuit function
  - qml.Hadamard, qml.CNOT for gates
  - qml.sample() or qml.probs() as return

Called by:
  - benchmarks/scripts/compile_all.py
  - benchmarks/notebooks/nb04_case_studies.ipynb (Case Study 1)
"""

import numpy as np
import pennylane as qml

dev = qml.device('default.qubit', wires=2)


@qml.qnode(dev)
def bell_state_circuit():
    """
    PennyLane Bell state QNode.

    Returns:
        np.ndarray: Probability distribution [P(|00⟩), P(|01⟩), P(|10⟩), P(|11⟩)].
    """
    qml.Hadamard(wires=0)
    qml.CNOT(wires=[0, 1])
    return qml.probs(wires=[0, 1])


def get_circuit():
    """Return the Bell state QNode for use by compile_all.py."""
    return bell_state_circuit


if __name__ == '__main__':
    probs = bell_state_circuit()
    print("Bell State probabilities:", probs)
    print(qml.draw(bell_state_circuit)())
    print(f"\nDevice: {dev.name}  |  Wires: {dev.num_wires}")
