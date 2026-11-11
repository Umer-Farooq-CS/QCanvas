"""
Cirq Implementation: GHZ State (variable: 3–8 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: GHZ State
Category: Foundational
Qubit Range: 3–8
Framework: Cirq (idiomatic style)

Called by:
  - benchmarks/scripts/compile_all.py  (n ∈ 3..8)
  - benchmarks/notebooks/nb03_statistical_analysis.ipynb
"""

import cirq


def get_circuit(n: int = 3):
    """
    Build the n-qubit GHZ state circuit in Cirq.

    Args:
        n: Number of qubits (3–8).

    Returns:
        cirq.Circuit: GHZ state preparation.
    """
    qubits = cirq.LineQubit.range(n)
    ops = [cirq.H(qubits[0])]
    for i in range(n - 1):
        ops.append(cirq.CNOT(qubits[i], qubits[i + 1]))
    ops.append(cirq.measure(*qubits, key='result'))
    return cirq.Circuit(ops)


if __name__ == '__main__':
    for n in [3, 4, 5]:
        c = get_circuit(n)
        print(f"\nGHZ state ({n} qubits):")
        print(c)
