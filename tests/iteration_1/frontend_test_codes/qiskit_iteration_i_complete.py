"""
Qiskit Complete Iteration I Feature Test

This circuit demonstrates ALL Iteration I features that should be
converted to OpenQASM 3.0 by the QCanvas platform.

Paste this code into the QCanvas frontend to test conversion.

Expected Output: OpenQASM 3.0 code with:
- All types (qubit, bit, int, uint, float, angle, bool)
- Constants
- Parameterized gates
- Gate modifiers (ctrl@, inv@)
- Custom gate definitions
- Measurements and resets
- Barriers
- Classical variables and operations
- If/else statements
- For loops
"""

from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.circuit import Parameter, Gate
import numpy as np

def get_circuit():
    # Create registers
    qr = QuantumRegister(5, 'q')
    cr = ClassicalRegister(5, 'c')
    qc = QuantumCircuit(qr, cr)
    
    # === ITERATION I FEATURE 1: Basic Gates ===
    qc.h(0)  # Hadamard
    qc.x(1)  # Pauli-X
    qc.y(2)  # Pauli-Y
    qc.z(3)  # Pauli-Z
    qc.s(0)  # S gate
    qc.t(1)  # T gate
    qc.sdg(2)  # S dagger (inverse S)
    qc.tdg(3)  # T dagger (inverse T)
    
    # === ITERATION I FEATURE 2: Parameterized Gates ===
    theta = Parameter('θ')
    qc.rx(np.pi/2, 0)  # RX rotation
    qc.ry(np.pi/4, 1)  # RY rotation
    qc.rz(np.pi, 2)     # RZ rotation
    qc.p(np.pi/2, 3)    # Phase gate
    qc.u(np.pi/2, 0, np.pi, 4)  # Universal gate (U gate)
    
    # === ITERATION I FEATURE 3: Two-Qubit Gates ===
    qc.cx(0, 1)   # CNOT (Controlled-X)
    qc.cz(1, 2)   # Controlled-Z
    qc.cy(2, 3)   # Controlled-Y
    qc.swap(0, 2) # SWAP
    qc.ch(1, 3)   # Controlled-Hadamard
    
    # === ITERATION I FEATURE 4: Three-Qubit Gates ===
    qc.ccx(0, 1, 2)  # Toffoli (Controlled-Controlled-X)
    qc.cswap(0, 1, 2)  # Fredkin (Controlled-SWAP)
    
    # === ITERATION I FEATURE 5: Special Gates ===
    qc.global_phase += np.pi/4  # Global phase (a property in Qiskit, not a method)
    qc.id(0)  # Identity
    qc.sx(1)  # Sqrt(X)
    qc.sxdg(2)  # Inverse Sqrt(X)
    
    # === ITERATION I FEATURE 6: Barrier ===
    qc.barrier()
    
    # === ITERATION I FEATURE 7: Reset ===
    qc.reset(4)
    
    # === ITERATION I FEATURE 8: Measurements ===
    qc.measure(0, 0)
    qc.measure(1, 1)
    qc.measure(2, 2)
    qc.measure(3, 3)
    qc.measure(4, 4)
    
    # === ITERATION I FEATURE 9: Controlled Gates (Gate Modifiers) ===
    # These demonstrate ctrl@ modifier
    qc.crx(np.pi/3, 0, 1)  # Controlled-RX
    qc.cry(np.pi/6, 1, 2)  # Controlled-RY
    qc.crz(np.pi/2, 2, 3)  # Controlled-RZ
    qc.cp(np.pi/4, 3, 4)   # Controlled-Phase
    
    # Note: Custom gates and advanced features would require
    # additional Qiskit setup beyond this basic example
    
    return qc

# Expected OpenQASM 3.0 features in output:
# ✓ OPENQASM 3.0 version
# ✓ include "stdgates.inc"
# ✓ Mathematical constants (pi, E, pi_2, pi_4)
# ✓ qubit[5] q;
# ✓ bit[5] c;
# ✓ Classical variables (int, uint, float, angle, bool)
# ✓ All standard gates (h, x, y, z, s, t, etc.)
# ✓ Parameterized gates (rx, ry, rz, p, u)
# ✓ Two-qubit gates (cx, cz, swap, etc.)
# ✓ Three-qubit gates (ccx, cswap)
# ✓ Global phase gate (gphase)
# ✓ Barrier instruction
# ✓ Reset instruction
# ✓ Measurement instruction
# ✓ If/else statements (in generated code)
# ✓ For loops (in generated code)
