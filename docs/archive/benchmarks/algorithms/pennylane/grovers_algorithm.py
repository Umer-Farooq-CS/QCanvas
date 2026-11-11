"""
PennyLane Implementation: Grover's Algorithm (variable: 2–6 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: Grover's Search Algorithm
Category: Search
Qubit Range: 2–6
Framework: PennyLane (idiomatic style)

Uses PennyLane's built-in qml.GroverOperator template for the diffusion operator,
which is the idiomatic PennyLane approach. The oracle is hand-built using
qml.FlipSign (or equivalent multi-controlled Z via qml.ctrl).

Uses the same MARKED_STATES as Qiskit and Cirq versions.

Called by: benchmarks/scripts/compile_all.py  (n ∈ 2..6)
"""

import numpy as np
import pennylane as qml

MARKED_STATES = {
    2: "11",
    3: "101",
    4: "1011",
    5: "10110",
    6: "101101",
}


def get_circuit(n: int = 2):
    """
    Create PennyLane Grover's algorithm QNode for n qubits.

    Uses qml.GroverOperator (idiomatic PennyLane) for diffusion.
    Oracle implemented via qml.Hadamard + qml.MultiControlledX + qml.Hadamard.

    Args:
        n: Number of search qubits (2–6).

    Returns:
        callable: PennyLane QNode.
    """
    if n not in MARKED_STATES:
        raise ValueError(f"n must be in {sorted(MARKED_STATES.keys())}")

    marked         = MARKED_STATES[n]
    num_iterations = max(1, int(np.floor(np.pi / 4 * np.sqrt(2 ** n))))
    wires          = list(range(n))
    dev            = qml.device('default.qubit', wires=n)

    # Zero-bit indices for this marked state
    zero_bits = [i for i, b in enumerate(marked) if b == '0']

    @qml.qnode(dev)
    def grover_circuit():
        # Initial superposition
        for w in wires:
            qml.Hadamard(wires=w)

        for _ in range(num_iterations):
            # --- Phase oracle ---
            # Flip zero-bits
            for z in zero_bits:
                qml.PauliX(wires=z)
            # Multi-controlled Z: H on last, MCX, H
            qml.Hadamard(wires=n - 1)
            qml.MultiControlledX(wires=wires)   # controls=wires[:-1], target=wires[-1]
            qml.Hadamard(wires=n - 1)
            # Undo zero-bit flips
            for z in zero_bits:
                qml.PauliX(wires=z)

            # --- Grover diffusion operator (PennyLane idiomatic) ---
            qml.GroverOperator(wires=wires)

        return qml.probs(wires=wires)

    return grover_circuit


if __name__ == '__main__':
    for n in [2, 3, 4]:
        qnode = get_circuit(n)
        iters = max(1, int(np.floor(np.pi / 4 * np.sqrt(2 ** n))))
        print(f"\nGrover's (n={n}, marked='{MARKED_STATES[n]}', iters={iters}):")
        print(qml.draw(qnode)())
