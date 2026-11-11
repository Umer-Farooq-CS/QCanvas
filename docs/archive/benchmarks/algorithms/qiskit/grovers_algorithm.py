"""
Qiskit Implementation: Grover's Algorithm (variable: 2–6 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: Grover's Search Algorithm
Category: Search
Qubit Range: 2–6
Framework: Qiskit (idiomatic style)

PRIMARY CASE STUDY for Paper 5 (Case Study 2).
Expected to show HIGHEST gate-count divergence across frameworks due to
different decompositions of the multi-controlled-Z in both oracle and diffusion.

Marked states (fixed for reproducibility across all framework files):
  n=2 → |11⟩    n=3 → |101⟩    n=4 → |1011⟩
  n=5 → |10110⟩  n=6 → |101101⟩

Called by:
  - benchmarks/scripts/compile_all.py  (n ∈ 2..6)
  - benchmarks/notebooks/nb04_case_studies.ipynb (Case Study 2)
  - benchmarks/notebooks/nb03_statistical_analysis.ipynb (scaling)
"""

import numpy as np
from qiskit import QuantumCircuit

# Fixed marked states — must match across Cirq and PennyLane files
MARKED_STATES = {
    2: "11",
    3: "101",
    4: "1011",
    5: "10110",
    6: "101101",
}


def build_phase_oracle(n: int, marked_state: str) -> QuantumCircuit:
    """
    Build the phase oracle that applies a -1 phase to the marked state.

    Strategy:
      1. X on qubits where marked_state[i] == '0' (flip 0-bits to 1)
      2. Multi-controlled-Z: phase flip only when all qubits are |1⟩
      3. X again to restore 0-bits

    Multi-controlled-Z implemented via: H on target, MCX (Toffoli chain), H.

    Args:
        n: Number of qubits.
        marked_state: Target bitstring (length n, big-endian).

    Returns:
        QuantumCircuit: n-qubit phase oracle.
    """
    oracle = QuantumCircuit(n, name='Oracle')

    # Flip zero-bits so that the marked state becomes all-1s
    for i, bit in enumerate(marked_state):
        if bit == '0':
            oracle.x(i)

    # Multi-controlled-Z: H on last qubit, MCX, H back
    oracle.h(n - 1)
    oracle.mcx(list(range(n - 1)), n - 1)
    oracle.h(n - 1)

    # Undo the X flips
    for i, bit in enumerate(marked_state):
        if bit == '0':
            oracle.x(i)

    return oracle


def build_diffusion_operator(n: int) -> QuantumCircuit:
    """
    Build the Grover diffusion operator: 2|s⟩⟨s| − I.

    Standard Qiskit decomposition:
      H⊗n → X⊗n → multi-controlled-Z (H + MCX + H) → X⊗n → H⊗n

    Args:
        n: Number of qubits.

    Returns:
        QuantumCircuit: n-qubit diffusion sub-circuit.
    """
    diff = QuantumCircuit(n, name='Diffusion')

    diff.h(range(n))
    diff.x(range(n))

    # Multi-controlled-Z
    diff.h(n - 1)
    diff.mcx(list(range(n - 1)), n - 1)
    diff.h(n - 1)

    diff.x(range(n))
    diff.h(range(n))

    return diff


def get_circuit(n: int = 2):
    """
    Build the full Grover's algorithm circuit for n qubits.

    Number of iterations: floor(π/4 × √(2^n))

    Args:
        n: Number of search qubits (2–6).

    Returns:
        QuantumCircuit: Full Grover circuit. Measurement should yield
            the marked state with probability > 80% (optimal iterations).
    """
    if n not in MARKED_STATES:
        raise ValueError(f"n must be in {sorted(MARKED_STATES.keys())}, got {n}")

    marked = MARKED_STATES[n]
    num_iterations = max(1, int(np.floor(np.pi / 4 * np.sqrt(2 ** n))))

    qc = QuantumCircuit(n, n)

    # Initial equal superposition
    qc.h(range(n))

    # Grover iterations
    oracle = build_phase_oracle(n, marked)
    diffusion = build_diffusion_operator(n)

    for _ in range(num_iterations):
        qc.compose(oracle,    qubits=range(n), inplace=True)
        qc.compose(diffusion, qubits=range(n), inplace=True)

    qc.measure(range(n), range(n))

    return qc


if __name__ == '__main__':
    for n in [2, 3, 4]:
        qc = get_circuit(n)
        iters = max(1, int(np.floor(np.pi / 4 * np.sqrt(2 ** n))))
        print(f"\nGrover's Algorithm (n={n}, marked='{MARKED_STATES[n]}', iters={iters}):")
        print(qc.draw('text'))
        print(f"  Gate count: {qc.count_ops()}")
        print(f"  Depth: {qc.depth()}")
