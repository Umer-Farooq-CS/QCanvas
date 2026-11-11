"""
Cirq Implementation: Deutsch–Jozsa Algorithm (variable: 3–8 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: Deutsch–Jozsa
Category: Oracle-Based
Qubit Range: 3–8 (n input qubits + 1 ancilla)
Framework: Cirq (idiomatic style)

Called by:
  - benchmarks/scripts/compile_all.py  (n ∈ 3..8)
  - benchmarks/notebooks/nb03_statistical_analysis.ipynb
"""

import cirq


def get_circuit(n: int = 3, oracle_type: str = 'balanced'):
    """
    Build the Deutsch–Jozsa circuit for n input qubits in Cirq.

    Args:
        n: Number of input qubits (3–8).
        oracle_type: 'balanced', 'constant_0', or 'constant_1'.

    Returns:
        cirq.Circuit: Full DJ circuit. All-zero measurement → constant.
    """
    inputs  = cirq.LineQubit.range(n)
    ancilla = cirq.LineQubit(n)

    ops = []

    # Initialise ancilla to |−⟩
    ops.append(cirq.X(ancilla))
    ops.extend(cirq.H(q) for q in inputs)
    ops.append(cirq.H(ancilla))

    # Oracle
    if oracle_type == 'balanced':
        for q in inputs:
            ops.append(cirq.CNOT(q, ancilla))
    elif oracle_type == 'constant_1':
        ops.append(cirq.X(ancilla))
    # constant_0: do nothing

    # Apply H to input qubits
    ops.extend(cirq.H(q) for q in inputs)

    # Measure input qubits
    ops.append(cirq.measure(*inputs, key='result'))

    return cirq.Circuit(ops)


if __name__ == '__main__':
    for n in [3, 4, 5]:
        c = get_circuit(n)
        print(f"\nDeutsch–Jozsa balanced (n={n}):")
        print(c)
