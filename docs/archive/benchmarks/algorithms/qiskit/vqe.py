"""
Qiskit Implementation: VQE – Variational Quantum Eigensolver (variable: 2–6 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: VQE (hardware-efficient ansatz)
Category: Variational
Qubit Range: 2–6
Framework: Qiskit (idiomatic style)

Hardware-efficient ansatz with:
  - Layer of Ry(θ) gates on all qubits (variational)
  - Layer of CX entangling gates (nearest-neighbour chain)
  - p=1 depth (single layer)

Parameters are set to fixed values (π/4) for structural benchmarking.
The purpose is NOT to find the ground state but to benchmark compilation
of a parameterised, entangling variational circuit.

Called by:
  - benchmarks/scripts/compile_all.py  (n ∈ 2..6)
  - benchmarks/notebooks/nb03_statistical_analysis.ipynb
"""

import numpy as np
from qiskit import QuantumCircuit
from qiskit.circuit import ParameterVector


def get_circuit(n: int = 2):
    """
    Build the hardware-efficient VQE ansatz for n qubits (p=1 layer).

    Args:
        n: Number of qubits (2–6).

    Returns:
        QuantumCircuit: VQE ansatz circuit with parameters bound to π/4.
    """
    if n < 2:
        raise ValueError(f"VQE requires n >= 2 qubits, got {n}")

    # Symbolic parameters
    theta = ParameterVector('θ', length=n)

    qc = QuantumCircuit(n, n)

    # Rotation layer: Ry(θ_i) on each qubit
    for i in range(n):
        qc.ry(theta[i], i)

    # Entanglement layer: CX chain
    for i in range(n - 1):
        qc.cx(i, i + 1)

    # Measure
    qc.measure(range(n), range(n))

    # Bind parameters to π/4 for structural benchmarking
    param_vals = {theta[i]: np.pi / 4 for i in range(n)}
    qc_bound = qc.assign_parameters(param_vals)

    return qc_bound


if __name__ == '__main__':
    for n in [2, 3, 4]:
        qc = get_circuit(n)
        print(f"\nVQE ansatz (n={n}, p=1):")
        print(qc.draw('text'))
        print(f"  Gate count: {qc.count_ops()}")
