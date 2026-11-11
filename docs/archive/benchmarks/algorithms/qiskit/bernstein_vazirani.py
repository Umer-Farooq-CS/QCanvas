"""
Qiskit Implementation: Bernstein–Vazirani Algorithm (variable: 3–8 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: Bernstein–Vazirani
Category: Oracle-Based
Qubit Range: 3–8 (n input qubits + 1 ancilla)
Framework: Qiskit (idiomatic style)

Recovers a hidden string s ∈ {0,1}^n from an oracle f(x) = s·x (mod 2)
in a single query, compared to n classical queries.

Fixed secret strings (for reproducibility across frameworks):
  n=3 → s = "101"
  n=4 → s = "1011"
  n=5 → s = "10110"
  n=6 → s = "101101"
  n=7 → s = "1011010"
  n=8 → s = "10110101"

Called by:
  - benchmarks/scripts/compile_all.py  (n ∈ 3..8)
  - benchmarks/notebooks/nb03_statistical_analysis.ipynb
"""

from qiskit import QuantumCircuit

# Fixed secret strings — must match across all three framework files
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
    Build the Bernstein–Vazirani circuit for n input qubits.

    After measurement, the input register should read the secret string s
    with probability 1 (deterministic algorithm).

    Args:
        n: Number of input qubits (3–8).

    Returns:
        QuantumCircuit: BV circuit. Measurement output = secret string s.
    """
    if n not in SECRET_STRINGS:
        raise ValueError(f"No secret string defined for n={n}. Use n ∈ {sorted(SECRET_STRINGS.keys())}.")

    s = SECRET_STRINGS[n]
    total = n + 1   # n input + 1 ancilla
    qc = QuantumCircuit(total, n)

    # Initialise ancilla to |−⟩
    qc.x(n)

    # Apply H to all qubits
    qc.h(range(total))

    # Oracle: CNOT from input qubit i to ancilla if s[i] == '1'
    for i, bit in enumerate(s):
        if bit == '1':
            qc.cx(i, n)

    # Apply H to input qubits only
    qc.h(range(n))

    # Measure input register — should reveal s
    qc.measure(range(n), range(n))

    return qc


if __name__ == '__main__':
    for n in [3, 4, 5]:
        qc = get_circuit(n)
        s = SECRET_STRINGS[n]
        print(f"\nBernstein–Vazirani (n={n}, secret='{s}'):")
        print(qc.draw('text'))
        print(f"  Gate count: {qc.count_ops()}")
