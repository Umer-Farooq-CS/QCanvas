"""
Qiskit Implementation: Deutsch–Jozsa Algorithm (variable: 3–8 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: Deutsch–Jozsa
Category: Oracle-Based
Qubit Range: 3–8 (n input qubits + 1 ancilla)
Framework: Qiskit (idiomatic style)

Determines whether a boolean function f: {0,1}^n → {0,1} is
constant (f always 0 or always 1) or balanced (f=0 for half inputs,
f=1 for the other half) in a single query.

Oracle types implemented:
  'balanced' → XOR oracle using CNOT gates (canonical balanced function)
  'constant_0' → f(x)=0 for all x (identity ancilla)
  'constant_1' → f(x)=1 for all x (X on ancilla before and after)

Idiomatic Qiskit:
  - n input qubits + 1 ancilla qubit (total n+1)
  - Ancilla initialised to |−⟩ (H applied after X)
  - Balanced oracle: CNOTs from all input qubits to ancilla

Called by:
  - benchmarks/scripts/compile_all.py  (n ∈ 3..8, oracle='balanced')
  - benchmarks/notebooks/nb03_statistical_analysis.ipynb
"""

from qiskit import QuantumCircuit


def build_oracle(n: int, oracle_type: str = 'balanced') -> QuantumCircuit:
    """
    Build the Deutsch-Jozsa oracle as a sub-circuit.

    Args:
        n: Number of input qubits.
        oracle_type: 'balanced', 'constant_0', or 'constant_1'.

    Returns:
        QuantumCircuit: Oracle sub-circuit acting on n+1 qubits.
    """
    oracle = QuantumCircuit(n + 1)

    if oracle_type == 'balanced':
        # CNOT from each input qubit to the ancilla (qubit n)
        for i in range(n):
            oracle.cx(i, n)
    elif oracle_type == 'constant_0':
        pass  # Identity: f(x) = 0 for all x
    elif oracle_type == 'constant_1':
        oracle.x(n)  # f(x) = 1 for all x: flip ancilla unconditionally
    else:
        raise ValueError(f"Unknown oracle type: {oracle_type}")

    return oracle


def get_circuit(n: int = 3, oracle_type: str = 'balanced'):
    """
    Build the full Deutsch–Jozsa circuit for n input qubits.

    Args:
        n: Number of input qubits (3–8).
        oracle_type: 'balanced' (default), 'constant_0', or 'constant_1'.

    Returns:
        QuantumCircuit: Full DJ circuit. Measuring all input qubits gives
            all-zeros → constant function; any other outcome → balanced.
    """
    if n < 1:
        raise ValueError(f"DJ requires n >= 1 input qubits, got {n}")

    total_qubits = n + 1   # n input + 1 ancilla
    qc = QuantumCircuit(total_qubits, n)

    # Initialise ancilla to |−⟩
    qc.x(n)

    # Apply H to all qubits (input + ancilla)
    qc.h(range(total_qubits))

    # Apply oracle
    oracle = build_oracle(n, oracle_type)
    qc.compose(oracle, qubits=range(total_qubits), inplace=True)

    # Apply H to input qubits only
    qc.h(range(n))

    # Measure input qubits
    qc.measure(range(n), range(n))

    return qc


if __name__ == '__main__':
    for n in [3, 4, 5]:
        qc = get_circuit(n, 'balanced')
        print(f"\nDeutsch–Jozsa balanced ({n} input qubits):")
        print(qc.draw('text'))
        print(f"  Gate count: {qc.count_ops()}")
