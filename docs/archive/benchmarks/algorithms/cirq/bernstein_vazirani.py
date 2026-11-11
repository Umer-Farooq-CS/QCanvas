"""
Cirq Implementation: Bernstein–Vazirani Algorithm (variable: 3–8 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: Bernstein–Vazirani
Category: Oracle-Based
Qubit Range: 3–8 (n input qubits + 1 ancilla)
Framework: Cirq (idiomatic style)

Uses the same fixed SECRET_STRINGS as the Qiskit and PennyLane versions
to ensure a fair cross-framework comparison.

Called by:
  - benchmarks/scripts/compile_all.py  (n ∈ 3..8)
  - benchmarks/notebooks/nb03_statistical_analysis.ipynb
"""

import cirq

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
    Build the Bernstein–Vazirani circuit for n input qubits in Cirq.

    Args:
        n: Number of input qubits (3–8).

    Returns:
        cirq.Circuit: BV circuit. Measurement = secret string s.
    """
    if n not in SECRET_STRINGS:
        raise ValueError(f"No secret string for n={n}. Use n ∈ {sorted(SECRET_STRINGS.keys())}.")

    s       = SECRET_STRINGS[n]
    inputs  = cirq.LineQubit.range(n)
    ancilla = cirq.LineQubit(n)
    ops     = []

    # Ancilla to |−⟩
    ops.append(cirq.X(ancilla))
    ops.extend(cirq.H(q) for q in inputs)
    ops.append(cirq.H(ancilla))

    # Oracle: CNOT from input[i] to ancilla if s[i] == '1'
    for i, bit in enumerate(s):
        if bit == '1':
            ops.append(cirq.CNOT(inputs[i], ancilla))

    # H on input qubits
    ops.extend(cirq.H(q) for q in inputs)

    # Measure
    ops.append(cirq.measure(*inputs, key='result'))

    return cirq.Circuit(ops)


if __name__ == '__main__':
    for n in [3, 4, 5]:
        c = get_circuit(n)
        print(f"\nBernstein–Vazirani (n={n}, secret='{SECRET_STRINGS[n]}'):")
        print(c)
