"""
Cirq Implementation: Bit-Flip Error Correction Code (3 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: 3-Qubit Bit-Flip Code
Category: Error Correction
Qubit Range: 3
Framework: Cirq (idiomatic style)

Encode → bit-flip error on q[0] → majority-vote correction → decode → measure.

Called by: benchmarks/scripts/compile_all.py
"""

import cirq


def get_circuit():
    """Build 3-qubit bit-flip code circuit in Cirq."""
    q0, q1, q2 = cirq.LineQubit.range(3)
    ops = []

    # Prepare |+⟩ on data qubit
    ops.append(cirq.H(q0))

    # Encoding: fan-out CNOTs
    ops.append(cirq.CNOT(q0, q1))
    ops.append(cirq.CNOT(q0, q2))

    # Simulated error: bit-flip on q0
    ops.append(cirq.X(q0))

    # Majority-vote correction via Toffoli (Fredkin approach)
    ops.append(cirq.CCX(q1, q2, q0))

    # Decoding
    ops.append(cirq.CNOT(q0, q1))
    ops.append(cirq.CNOT(q0, q2))

    # Measure
    ops.append(cirq.measure(q0, q1, q2, key='result'))

    return cirq.Circuit(ops)


if __name__ == '__main__':
    c = get_circuit()
    print(c)
