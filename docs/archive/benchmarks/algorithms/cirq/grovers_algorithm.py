"""
Cirq Implementation: Grover's Algorithm (variable: 2–6 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: Grover's Search Algorithm
Category: Search
Qubit Range: 2–6
Framework: Cirq (idiomatic style)

Cirq-idiomatic decomposition:
  - Uses cirq.X, cirq.H natively
  - Multi-controlled Z: Cirq's cirq.ControlledGate for n-controlled gates
  - Oracle applied as a custom Gate built from basic Cirq operations

Uses the same MARKED_STATES as Qiskit and PennyLane versions.

Called by:
  - benchmarks/scripts/compile_all.py  (n ∈ 2..6)
  - benchmarks/notebooks/nb04_case_studies.ipynb (Case Study 2)
"""

import numpy as np
import cirq

MARKED_STATES = {
    2: "11",
    3: "101",
    4: "1011",
    5: "10110",
    6: "101101",
}


def _mcz(qubits):
    """Multi-controlled Z on a list of qubits using decomposition."""
    if len(qubits) == 1:
        return [cirq.Z(qubits[0])]
    # H on last qubit, then MCX (multi-controlled X), then H
    ops = []
    target = qubits[-1]
    controls = qubits[:-1]
    ops.append(cirq.H(target))
    if len(controls) == 1:
        ops.append(cirq.CNOT(controls[0], target))
    elif len(controls) == 2:
        ops.append(cirq.CCX(controls[0], controls[1], target))
    else:
        # For > 2 controls, use recursive decomposition
        ops.append(cirq.ControlledGate(cirq.X, num_controls=len(controls))(*controls, target))
    ops.append(cirq.H(target))
    return ops


def build_phase_oracle(qubits, marked_state: str) -> list:
    """Phase oracle operations for the given marked state."""
    ops = []
    # X on qubits where marked_state[i] == '0'
    for i, bit in enumerate(marked_state):
        if bit == '0':
            ops.append(cirq.X(qubits[i]))
    # Multi-controlled Z
    ops.extend(_mcz(list(qubits)))
    # Undo X flips
    for i, bit in enumerate(marked_state):
        if bit == '0':
            ops.append(cirq.X(qubits[i]))
    return ops


def build_diffusion(qubits) -> list:
    """Grover diffusion operator operations."""
    ops = []
    ops.extend(cirq.H(q) for q in qubits)
    ops.extend(cirq.X(q) for q in qubits)
    ops.extend(_mcz(list(qubits)))
    ops.extend(cirq.X(q) for q in qubits)
    ops.extend(cirq.H(q) for q in qubits)
    return ops


def get_circuit(n: int = 2):
    """
    Build Grover's algorithm circuit for n qubits in Cirq.

    Args:
        n: Number of search qubits (2–6).

    Returns:
        cirq.Circuit: Full Grover circuit.
    """
    if n not in MARKED_STATES:
        raise ValueError(f"n must be in {sorted(MARKED_STATES.keys())}, got {n}")

    marked = MARKED_STATES[n]
    num_iterations = max(1, int(np.floor(np.pi / 4 * np.sqrt(2 ** n))))
    qubits = cirq.LineQubit.range(n)

    ops = list(cirq.H(q) for q in qubits)

    for _ in range(num_iterations):
        ops.extend(build_phase_oracle(qubits, marked))
        ops.extend(build_diffusion(qubits))

    ops.append(cirq.measure(*qubits, key='result'))

    return cirq.Circuit(ops)


if __name__ == '__main__':
    for n in [2, 3, 4]:
        c = get_circuit(n)
        iters = max(1, int(np.floor(np.pi / 4 * np.sqrt(2 ** n))))
        print(f"\nGrover's (n={n}, marked='{MARKED_STATES[n]}', iters={iters}):")
        print(c)
