"""
Cirq Implementation: Bell State (2 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: Bell State
Category: Foundational
Qubit Range: 2
Framework: Cirq (idiomatic style — moment-based, LineQubit)

Idiomatic Cirq conventions:
  - cirq.LineQubit for qubit allocation
  - cirq.Circuit with explicit list of operations
  - cirq.CNOT (not cx — Cirq uses full names)
  - cirq.measure() with a string key
  - Natural big-endian bitstring ordering (no reversal needed)

Called by:
  - benchmarks/scripts/compile_all.py
  - benchmarks/notebooks/nb04_case_studies.ipynb (Case Study 1)
"""

import cirq


def get_circuit():
    """
    Build and return the Cirq Bell state circuit.

    Returns:
        cirq.Circuit: 2-qubit Bell state |Φ+⟩ preparation circuit.
    """
    q0, q1 = cirq.LineQubit.range(2)

    circuit = cirq.Circuit([
        cirq.H(q0),
        cirq.CNOT(q0, q1),
        cirq.measure(q0, q1, key='result'),
    ])

    return circuit


if __name__ == '__main__':
    c = get_circuit()
    print(c)
    print(f"\nMoments: {len(c)}  |  Qubits: {len(c.all_qubits())}")
