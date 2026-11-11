"""
Qiskit Implementation: Bell State (2 qubits)
Paper 5 – Cross-Framework Quantum Algorithm Benchmarking

Algorithm: Bell State
Category: Foundational
Qubit Range: 2
Framework: Qiskit (idiomatic style)

Expected output distribution:
  |00⟩ → ~50%
  |11⟩ → ~50%
  (after bit-reversal correction for Qiskit's little-endian convention)

Called by:
  - benchmarks/scripts/compile_all.py
  - benchmarks/notebooks/nb01_compile_and_static_analysis.ipynb
  - benchmarks/notebooks/nb04_case_studies.ipynb (Case Study 1)
"""

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister


def get_circuit():
    """
    Build and return the Qiskit Bell state circuit.

    Returns:
        QuantumCircuit: 2-qubit circuit preparing |Φ+⟩ = (|00⟩ + |11⟩) / √2.
    """
    qr = QuantumRegister(2, 'q')
    cr = ClassicalRegister(2, 'c')
    qc = QuantumCircuit(qr, cr)

    qc.h(qr[0])
    qc.cx(qr[0], qr[1])
    qc.measure(qr, cr)

    return qc


if __name__ == '__main__':
    qc = get_circuit()
    print(qc.draw('text'))
    print(f"\nQubits: {qc.num_qubits}  |  Classical bits: {qc.num_clbits}")
    print(f"Gate count: {qc.count_ops()}")
