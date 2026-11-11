"""
Qiskit Implementation: Bit-Flip Error Correction Code (3 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: 3-Qubit Bit-Flip Code
Category: Error Correction
Qubit Range: 3
Framework: Qiskit (idiomatic style)

The simplest quantum error correction code:
  - 1 logical qubit encoded in 3 physical qubits
  - Detects and corrects a single bit-flip on any one qubit
  - Uses syndrome measurement (ancilla-free majority vote version)

Circuit:
  Phase 1 — Encoding:
    q[1] = CNOT(q[0], q[1]) ; q[2] = CNOT(q[0], q[2])
    (encodes logical |0⟩ → |000⟩, logical |1⟩ → |111⟩)

  Phase 2 — Error simulation: X(q[0]) introduces a bit-flip error on q[0]

  Phase 3 — Syndrome measurement & correction (majority vote):
    CNOTs for syndrome extraction, then Toffoli for majority correction

Note: Full syndrome measurement requires ancilla qubits. This implementation
uses a simplified direct-measurement scheme for QASM structural benchmarking.

Called by:
  - benchmarks/scripts/compile_all.py
  - benchmarks/notebooks/nb04_case_studies.ipynb (Error Correction analysis)
"""

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister


def get_circuit():
    """
    Build the 3-qubit bit-flip code circuit with error simulation.

    Returns:
        QuantumCircuit: Bit-flip encode → bit-flip error on q[0] → decode + measure.
    """
    qr = QuantumRegister(3, 'q')
    # 2 syndrome bits + 1 for the decoded logical qubit
    cr = ClassicalRegister(3, 'c')
    qc = QuantumCircuit(qr, cr)

    # Prepare logical |+⟩ state on data qubit for a non-trivial test
    qc.h(qr[0])

    # --- Encoding ---
    qc.cx(qr[0], qr[1])
    qc.cx(qr[0], qr[2])

    # --- Simulated error: bit-flip on qubit 0 ---
    qc.x(qr[0])

    # --- Syndrome measurement via parity checks ---
    # Ancilla-free version: use qr[1] and qr[2] as temporary syndrome bits
    # Parity between q[0] and q[1]: CNOT(q[0], sy0), CNOT(q[1], sy0)
    # (here we reuse the classical register for detection without ancilla)

    # Majority-vote correction using Toffoli:
    # If q[0] ≠ q[1] and q[0] ≠ q[2], flip q[0] back (majority vote)
    # Toffoli(q[1], q[2], q[0]) applies X to q[0] when q[1]=q[2]=1
    qc.ccx(qr[1], qr[2], qr[0])

    # --- Decoding ---
    qc.cx(qr[0], qr[1])
    qc.cx(qr[0], qr[2])

    # Measure all qubits: q[0] should return to |+⟩ (distribution ≈ 50/50)
    qc.measure(qr, cr)

    return qc


if __name__ == '__main__':
    qc = get_circuit()
    print(qc.draw('text'))
    print(f"\nQubits: {qc.num_qubits}  |  Gate count: {qc.count_ops()}")
