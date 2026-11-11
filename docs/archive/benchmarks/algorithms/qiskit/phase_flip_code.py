"""
Qiskit Implementation: Phase-Flip Error Correction Code (3 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: 3-Qubit Phase-Flip Code
Category: Error Correction
Qubit Range: 3
Framework: Qiskit (idiomatic style)

The 3-qubit phase-flip code corrects a single Z (phase-flip) error.
It is the Hadamard-conjugate of the bit-flip code:
  - Encode by wrapping the bit-flip encoding in Hadamard gates
  - In the H basis, phase-flip becomes a bit-flip → same correction circuit

Circuit:
  Phase 1 — Encoding:
    H on q[0], then fan-out CNOTs, then H on all qubits
  Phase 2 — Error simulation: Z(q[0]) on q[0] in the Z-basis
  Phase 3 — Decoding and correction (reverse encoding + Toffoli)

Called by:
  - benchmarks/scripts/compile_all.py
  - benchmarks/notebooks/nb04_case_studies.ipynb
"""

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister


def get_circuit():
    """
    Build the 3-qubit phase-flip error correction circuit.

    Returns:
        QuantumCircuit: Phase-flip encode → phase-flip error → correct + measure.
    """
    qr = QuantumRegister(3, 'q')
    cr = ClassicalRegister(3, 'c')
    qc = QuantumCircuit(qr, cr)

    # Prepare logical |+⟩ on data qubit
    qc.h(qr[0])

    # --- Encoding (H-basis bit-flip code) ---
    qc.cx(qr[0], qr[1])
    qc.cx(qr[0], qr[2])
    qc.h(qr[0])
    qc.h(qr[1])
    qc.h(qr[2])

    # --- Simulated single-qubit Z error on qubit 0 ---
    qc.z(qr[0])

    # --- Decoding ---
    qc.h(qr[0])
    qc.h(qr[1])
    qc.h(qr[2])

    # Toffoli correction (same as bit-flip code in H basis)
    qc.ccx(qr[1], qr[2], qr[0])

    qc.cx(qr[0], qr[1])
    qc.cx(qr[0], qr[2])

    # Measure
    qc.measure(qr, cr)

    return qc


if __name__ == '__main__':
    qc = get_circuit()
    print(qc.draw('text'))
    print(f"\nQubits: {qc.num_qubits}  |  Gate count: {qc.count_ops()}")
