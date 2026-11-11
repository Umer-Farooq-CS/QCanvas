"""
Cirq Implementation: Quantum Teleportation (3 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: Quantum Teleportation
Category: Quantum Communication
Qubit Range: 3
Framework: Cirq (idiomatic style)

Cirq uses ClassicallyControlledOperation for conditional gates,
which is different from Qiskit's c_if() syntax — this is a key
QASM structural difference captured by compile_all.py.

Called by:
  - benchmarks/scripts/compile_all.py
  - benchmarks/notebooks/nb04_case_studies.ipynb
"""

import cirq


def get_circuit():
    """
    Build the 3-qubit quantum teleportation circuit in Cirq.

    Returns:
        cirq.Circuit: Teleportation with ClassicallyControlledOperation.
    """
    q0, q1, q2 = cirq.LineQubit.range(3)

    # Classical bits for Alice's measurement results
    m0 = cirq.measure(q0, key='m0')
    m1 = cirq.measure(q1, key='m1')

    circuit = cirq.Circuit([
        # Prepare state to teleport (|+⟩ on q0)
        cirq.H(q0),

        # Bell pair between Alice (q1) and Bob (q2)
        cirq.H(q1),
        cirq.CNOT(q1, q2),

        # Alice's Bell measurement
        cirq.CNOT(q0, q1),
        cirq.H(q0),
        m0,
        m1,

        # Bob's corrections (classically controlled)
        cirq.X(q2).on(q2).with_classical_controls('m1'),
        cirq.Z(q2).on(q2).with_classical_controls('m0'),

        # Bob measures
        cirq.measure(q2, key='teleported'),
    ])

    return circuit


if __name__ == '__main__':
    c = get_circuit()
    print(c)
