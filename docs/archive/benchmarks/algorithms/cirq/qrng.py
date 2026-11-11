"""
Cirq Implementation: QRNG (variable: 4–8 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: QRNG (Quantum Random Number Generator)
Category: Randomness
Qubit Range: 4–8
Framework: Cirq (idiomatic style)

Cirq convention: ops are created in a list and passed to cirq.Circuit().

Called by: benchmarks/scripts/compile_all.py  (n ∈ 4..8)
"""

import cirq


def get_circuit(n: int = 4):
    """Build n-qubit QRNG circuit in Cirq."""
    qubits = cirq.LineQubit.range(n)
    ops = [cirq.H(q) for q in qubits]
    ops.append(cirq.measure(*qubits, key='result'))
    return cirq.Circuit(ops)


if __name__ == '__main__':
    for n in [4, 5, 6]:
        c = get_circuit(n)
        print(f"\nQRNG ({n} qubits):")
        print(c)
