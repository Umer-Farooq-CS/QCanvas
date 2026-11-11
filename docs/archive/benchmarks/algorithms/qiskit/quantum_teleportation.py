"""
Qiskit Implementation: Quantum Teleportation (3 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: Quantum Teleportation
Category: Quantum Communication
Qubit Range: 3
Framework: Qiskit (idiomatic style)

Circuit structure:
  q[0] = qubit to teleport (initialised to |+⟩ for a non-trivial state)
  q[1] = Alice's Bell pair qubit
  q[2] = Bob's Bell pair qubit

  Phase 1: Prepare Bell pair between Alice (q[1]) and Bob (q[2])
  Phase 2: Alice entangles her qubit q[0] with q[1], measures both
  Phase 3: Bob applies corrections conditionally on Alice's measurement results

Idiomatic Qiskit: Uses c_if() for classically-controlled corrections.

Called by:
  - benchmarks/scripts/compile_all.py
  - benchmarks/notebooks/nb04_case_studies.ipynb
"""

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister


def get_circuit():
    """
    Build and return the 3-qubit quantum teleportation circuit.

    Returns:
        QuantumCircuit: Teleportation protocol with classical feed-forward.
    """
    qr = QuantumRegister(3, 'q')
    cr = ClassicalRegister(3, 'c')
    qc = QuantumCircuit(qr, cr)

    # --- Prepare state to teleport: |+⟩ on q[0] ---
    qc.h(qr[0])

    # --- Create Bell pair between Alice (q[1]) and Bob (q[2]) ---
    qc.h(qr[1])
    qc.cx(qr[1], qr[2])

    # --- Alice's operations ---
    qc.cx(qr[0], qr[1])
    qc.h(qr[0])

    # --- Measure Alice's qubits ---
    qc.measure(qr[0], cr[0])
    qc.measure(qr[1], cr[1])

    # --- Bob's corrections (classically controlled) ---
    # Apply X if cr[1] == 1
    qc.x(qr[2]).c_if(cr[1], 1)
    # Apply Z if cr[0] == 1
    qc.z(qr[2]).c_if(cr[0], 1)

    # --- Measure Bob's qubit ---
    qc.measure(qr[2], cr[2])

    return qc


if __name__ == '__main__':
    qc = get_circuit()
    print(qc.draw('text'))
    print(f"\nQubits: {qc.num_qubits}  |  Gate count: {qc.count_ops()}")
