"""
Cirq Implementation: VQE – Variational Quantum Eigensolver (variable: 2–6 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: VQE (hardware-efficient ansatz, p=1)
Category: Variational
Qubit Range: 2–6
Framework: Cirq (idiomatic style)

Cirq uses cirq.Ry and cirq.CX operations directly.
Parameters bound to π/4 for structural benchmarking.

Called by: benchmarks/scripts/compile_all.py  (n ∈ 2..6)
"""

import numpy as np
import cirq


def get_circuit(n: int = 2):
    """
    Build VQE hardware-efficient ansatz for n qubits in Cirq.

    Args:
        n: Number of qubits (2–6).

    Returns:
        cirq.Circuit: VQE ansatz with Ry layer + CX chain + measurement.
    """
    qubits = cirq.LineQubit.range(n)
    theta = np.pi / 4   # fixed parameter

    ops = []

    # Rotation layer: Ry(θ) on each qubit
    ops.extend(cirq.Ry(rads=theta)(q) for q in qubits)

    # Entanglement layer: CNOT chain
    for i in range(n - 1):
        ops.append(cirq.CNOT(qubits[i], qubits[i + 1]))

    # Measure
    ops.append(cirq.measure(*qubits, key='result'))

    return cirq.Circuit(ops)


if __name__ == '__main__':
    for n in [2, 3, 4]:
        c = get_circuit(n)
        print(f"\nVQE ansatz ({n} qubits):")
        print(c)
