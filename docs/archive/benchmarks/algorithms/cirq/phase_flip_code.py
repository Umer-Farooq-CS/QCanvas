"""
Cirq Implementation: Phase-Flip Error Correction Code (3 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: 3-Qubit Phase-Flip Code
Category: Error Correction
Qubit Range: 3
Framework: Cirq (idiomatic style)

Encode (H basis) → phase-flip error → correct (Toffoli) → decode → measure.

Called by: benchmarks/scripts/compile_all.py
"""

import cirq


def get_circuit():
    """Build 3-qubit phase-flip code circuit in Cirq."""
    q0, q1, q2 = cirq.LineQubit.range(3)
    ops = []

    # Prepare |+⟩
    ops.append(cirq.H(q0))

    # Encoding: fan-out then Hadamard all
    ops.append(cirq.CNOT(q0, q1))
    ops.append(cirq.CNOT(q0, q2))
    ops.extend([cirq.H(q0), cirq.H(q1), cirq.H(q2)])

    # Simulated error: Z on q0
    ops.append(cirq.Z(q0))

    # Decoding: H back, then Toffoli correction
    ops.extend([cirq.H(q0), cirq.H(q1), cirq.H(q2)])
    ops.append(cirq.CCX(q1, q2, q0))
    ops.append(cirq.CNOT(q0, q1))
    ops.append(cirq.CNOT(q0, q2))

    # Measure
    ops.append(cirq.measure(q0, q1, q2, key='result'))

    return cirq.Circuit(ops)


if __name__ == '__main__':
    c = get_circuit()
    print(c)
