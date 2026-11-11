"""
Qiskit Implementation: GHZ State (variable: 3–8 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: GHZ (Greenberger–Horne–Zeilinger) State
Category: Foundational
Qubit Range: 3–8
Framework: Qiskit (idiomatic style)

Used for entanglement scaling analysis (RQ4).

Expected output distribution:
  |00...0⟩ → ~50%
  |11...1⟩ → ~50%

Called by:
  - benchmarks/scripts/compile_all.py  (n ∈ 3..8)
  - benchmarks/notebooks/nb03_statistical_analysis.ipynb (scaling analysis)
"""

from qiskit import QuantumCircuit


def get_circuit(n: int = 3):
    """
    Build and return the Qiskit GHZ state circuit for n qubits.

    Args:
        n (int): Number of qubits (3–8). Default 3.

    Returns:
        QuantumCircuit: n-qubit GHZ state circuit.
    """
    if n < 2:
        raise ValueError(f"GHZ state requires n >= 2 qubits, got {n}")

    qc = QuantumCircuit(n, n)

    # Equal superposition on qubit 0
    qc.h(0)

    # Chain of CNOT gates: entangle each subsequent qubit
    for i in range(n - 1):
        qc.cx(i, i + 1)

    qc.measure_all()

    return qc


if __name__ == '__main__':
    for n in [3, 4, 5]:
        qc = get_circuit(n)
        print(f"\nGHZ state ({n} qubits):")
        print(qc.draw('text'))
        print(f"  Gate count: {qc.count_ops()}")
