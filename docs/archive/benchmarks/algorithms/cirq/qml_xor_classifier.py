"""
Cirq Implementation: QML XOR Classifier (variable: 2–4 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: QML XOR Classifier (angle encoding + variational layer)
Category: Quantum Machine Learning
Qubit Range: 2–4
Framework: Cirq (idiomatic style)

Same circuit structure as Qiskit version:
  Ry(x_i * π) encoding → CX chain → Rz(θ_i) → measure q[0]

Called by: benchmarks/scripts/compile_all.py  (n ∈ 2..4)
"""

import numpy as np
import cirq

DATA_POINT = [0.5, 0.3, 0.7, 0.2]


def get_circuit(n: int = 2):
    """Build n-qubit QML XOR classifier circuit in Cirq."""
    qubits = cirq.LineQubit.range(n)
    x      = DATA_POINT[:n]
    theta  = [np.pi / 4] * n
    ops    = []

    # Angle encoding
    ops.extend(cirq.Ry(rads=x[i] * np.pi)(qubits[i]) for i in range(n))

    # CX entanglement chain
    for i in range(n - 1):
        ops.append(cirq.CNOT(qubits[i], qubits[i + 1]))

    # Variational Rz layer
    ops.extend(cirq.rz(theta[i])(qubits[i]) for i in range(n))

    # Measure qubit 0
    ops.append(cirq.measure(qubits[0], key='result'))

    return cirq.Circuit(ops)


if __name__ == '__main__':
    for n in [2, 3, 4]:
        print(f"\nQML XOR Classifier ({n} qubits):")
        print(get_circuit(n))
