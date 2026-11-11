"""
Workshop example programs and their expected measurement distributions.

The programs are copied verbatim from the IDE's shipped examples:
  - frontend/lib/store.ts            (initialFiles, non-hybrid)
  - frontend/lib/fileTemplates.ts    (FILE_TEMPLATES_PRESETS)
  - frontend/app/examples/page.tsx   (examples, non-"Hybrid" category)
plus a few extra textbook circuits (GHZ-3, Bernstein-Vazirani, constant DJ,
ry(pi/3), real feed-forward teleportation) written for each framework.

Bitstring convention used by qsim's run_qasm (all three backends):
  key[i] == value of classical bit c[i]  (c[0] is the LEFT-most character).
If a program has no measurements, the backend samples every qubit and
key[i] == value of qubit q[i].

Expected distributions were derived by hand from the circuit; see the
comment next to each entry.
"""

import math
from itertools import product

import numpy as np


def uniform(n_bits):
    """Uniform distribution over all n-bit strings."""
    p = 1.0 / (2 ** n_bits)
    return {"".join(bits): p for bits in product("01", repeat=n_bits)}


def _qml_xor_expected():
    """Exact distribution of the 'QML XOR Classifier' example (c0 c1)."""
    def ry(t):
        c, s = math.cos(t / 2), math.sin(t / 2)
        return np.array([[c, -s], [s, c]], dtype=complex)

    def rx(t):
        c, s = math.cos(t / 2), math.sin(t / 2)
        return np.array([[c, -1j * s], [-1j * s, c]], dtype=complex)

    # Basis index = 2*q0 + q1 (q0 is the left/most-significant bit).
    def on(g0, g1):
        return np.kron(g0, g1)

    cnot = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 0, 1], [0, 0, 1, 0]], dtype=complex)
    state = np.zeros(4, dtype=complex)
    state[0] = 1
    state = on(rx(0), rx(math.pi)) @ state
    state = on(ry(0.5), ry(0.5)) @ state
    state = cnot @ state
    state = on(ry(0.5), ry(0.5)) @ state
    probs = np.abs(state) ** 2
    return {format(i, "02b"): float(p) for i, p in enumerate(probs) if p > 1e-12}


BELL = {"00": 0.5, "11": 0.5}

# ---------------------------------------------------------------------------
# Programs shipped with the IDE
# ---------------------------------------------------------------------------

PROGRAMS = []


def _add(pid, framework, source, code, expected, note=""):
    PROGRAMS.append({
        "id": pid,
        "framework": framework,
        "source": source,
        "code": code,
        "expected": expected,
        "note": note,
    })


# store.ts initialFiles -------------------------------------------------------
_add("store/bell_state_cirq", "cirq", "frontend/lib/store.ts", '''import cirq

# Create qubits
q0, q1 = cirq.LineQubit.range(2)

# Create Bell state circuit
circuit = cirq.Circuit(
    cirq.H(q0),           # Hadamard on first qubit
    cirq.CNOT(q0, q1),    # CNOT with q0 as control
    cirq.measure(q0, q1)  # Measure both qubits
)

print("Bell State Circuit (Cirq):")
print(circuit)
''', BELL)

_add("store/deutsch_jozsa_qiskit", "qiskit", "frontend/lib/store.ts", '''from qiskit import QuantumCircuit

# 3 qubits, 2 classical bits (only measure input qubits)
qc = QuantumCircuit(3, 2)

# STEP 1: Initialize ancilla to |1⟩
qc.x(2)

# STEP 2: Hadamard on all qubits
for i in range(3):
    qc.h(i)

# STEP 3: Balanced Oracle
qc.cx(0, 2)
qc.cx(1, 2)

# STEP 4: Hadamard on input qubits
qc.h(0)
qc.h(1)

# STEP 5: Measure input qubits
qc.measure(0, 0)
qc.measure(1, 1)
''', {"11": 1.0}, "balanced f(x)=x0^x1 -> |11>")

_add("store/grovers_search_pennylane", "pennylane", "frontend/lib/store.ts", '''import pennylane as qml

dev = qml.device("default.qubit", wires=2)

@qml.qnode(dev)
def grover_circuit():
    # STEP 1: Initialize superposition
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)

    # STEP 2: Oracle - mark |11⟩
    qml.CZ(wires=[0, 1])

    # STEP 3: Diffusion Operator
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    qml.PauliX(wires=0)
    qml.PauliX(wires=1)
    qml.CZ(wires=[0, 1])
    qml.PauliX(wires=0)
    qml.PauliX(wires=1)
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)

    # STEP 4: Measure
    qml.measure(wires=0)
    qml.measure(wires=1)
''', {"11": 1.0})

# fileTemplates.ts --------------------------------------------------------------
TELEPORT_QISKIT = '''from qiskit import QuantumCircuit

# Create circuit with 3 qubits and 3 classical bits
qc = QuantumCircuit(3, 3)

# STEP 1: Prepare the state to teleport (|+⟩ state as example)
qc.h(0)

# STEP 2: Create Bell pair between q1 and q2
qc.h(1)
qc.cx(1, 2)

# STEP 3: Bell measurement
qc.cx(0, 1)
qc.h(0)

# STEP 4: Measure qubits 0 and 1
qc.measure(0, 0)
qc.measure(1, 1)

# STEP 5: Conditional corrections (classical control)
c = [0, 0, 0]
if c[1] == 1:
    qc.x(2)
if c[0] == 1:
    qc.z(2)

# STEP 6: Final measurement
qc.measure(2, 2)
'''
_add("templates/quantum_teleportation_qiskit", "qiskit", "frontend/lib/fileTemplates.ts",
     TELEPORT_QISKIT, uniform(3),
     "teleports |+>; measured in Z every one of the 8 outcomes has p=1/8 (with or without corrections)")

QRNG_CIRQ = '''import cirq

# Number of random bits to generate
n_bits = 8

# Create n_bits qubits
qubits = cirq.LineQubit.range(n_bits)

circuit = cirq.Circuit()

# Put each qubit in superposition
for i in range(n_bits):
    circuit.append(cirq.H(cirq.LineQubit(i)))

# Measure all qubits
for i in range(n_bits):
    circuit.append(cirq.measure(cirq.LineQubit(i), key=f'c{i}'))
'''
_add("templates/qrng_cirq", "cirq", "frontend/lib/fileTemplates.ts", QRNG_CIRQ, uniform(8))

XOR_DEMO_PL = '''import pennylane as qml

dev = qml.device("default.qubit", wires=2)

@qml.qnode(dev)
def xor_demo_circuit():
    # STEP 1: Create Bell state (|00⟩ + |11⟩)/√2
    # Hadamard creates superposition, CNOT entangles qubits
    qml.Hadamard(wires=0)
    qml.CNOT(wires=[0, 1])

    # STEP 2: Flip qubit 0 to get (|10⟩ + |01⟩)/√2
    # Now qubits are always opposite (XOR = 1)
    qml.PauliX(wires=0)

    # STEP 3: Measure both qubits
    # Results will be either |01⟩ or |10⟩
    qml.measure(wires=0)
    qml.measure(wires=1)
'''
_add("templates/xor_demo_pennylane", "pennylane", "frontend/lib/fileTemplates.ts",
     XOR_DEMO_PL, {"01": 0.5, "10": 0.5})

QML_XOR_PL = '''import pennylane as qml
import numpy as np

dev = qml.device("default.qubit", wires=2)

@qml.qnode(dev)
def qml_xor_classifier():
    # ENCODING LAYER: Convert classical inputs to quantum states
    # Testing XOR(0, 1) - expect output = 1
    qml.RX(0, wires=0)              # Input x1=0: RX(0*π) = no rotation
    qml.RX(np.pi, wires=1)          # Input x2=1: RX(1*π) = flip to |1⟩

    # VARIATIONAL LAYER: Trainable gates that learn XOR pattern
    # Weights = 0.5 radians (found through gradient descent training)
    qml.RY(0.5, wires=0)            # Trainable rotation on qubit 0
    qml.RY(0.5, wires=1)            # Trainable rotation on qubit 1
    qml.CNOT(wires=[0, 1])          # Entanglement creates non-linear behavior
    qml.RY(0.5, wires=0)            # Second layer of trainable rotations
    qml.RY(0.5, wires=1)

    # MEASUREMENT: Read the XOR prediction from qubit 1
    # q[1] = 1 means XOR(x1, x2) = 1
    qml.measure(wires=0)
    qml.measure(wires=1)
'''
_add("templates/qml_xor_classifier_pennylane", "pennylane", "frontend/lib/fileTemplates.ts",
     QML_XOR_PL, _qml_xor_expected(), "exact numpy statevector of the same gate sequence")

BELL_QISKIT_SIMPLE = '''from qiskit import QuantumCircuit

qc = QuantumCircuit(2, 2)

# Create Bell state: (|00> + |11>)/sqrt(2)
qc.h(0)
qc.cx(0, 1)

# Measure
qc.measure(0, 0)
qc.measure(1, 1)
'''
_add("templates/bell_state_qiskit", "qiskit", "frontend/lib/fileTemplates.ts", BELL_QISKIT_SIMPLE, BELL)

_add("templates/bell_state_cirq", "cirq", "frontend/lib/fileTemplates.ts", '''import cirq

q0, q1 = cirq.LineQubit.range(2)

circuit = cirq.Circuit()
circuit.append(cirq.H(q0))
circuit.append(cirq.CNOT(q0, q1))
circuit.append(cirq.measure(q0, key='q0'))
circuit.append(cirq.measure(q1, key='q1'))
''', BELL)

_add("templates/bell_state_pennylane", "pennylane", "frontend/lib/fileTemplates.ts", '''import pennylane as qml

dev = qml.device('default.qubit', wires=2)

@qml.qnode(dev)
def bell_state():
    qml.Hadamard(wires=0)
    qml.CNOT(wires=[0, 1])
    qml.measure(wires=0)
    qml.measure(wires=1)
''', BELL)

_add("templates/deutsch_jozsa_qiskit", "qiskit", "frontend/lib/fileTemplates.ts", '''from qiskit import QuantumCircuit

n = 3
qc = QuantumCircuit(n + 1, n)

# Initialize ancilla in |1>
qc.x(n)

# Superposition
for i in range(n + 1):
    qc.h(i)

# Example balanced oracle
for i in range(n):
    qc.cx(i, n)

# Interference
for i in range(n):
    qc.h(i)

# Measure query qubits
for i in range(n):
    qc.measure(i, i)
''', {"111": 1.0}, "balanced f(x)=x0^x1^x2 -> |111>")

GROVER_QISKIT_TEMPLATE = '''from qiskit import QuantumCircuit

qc = QuantumCircuit(2, 2)

# Uniform superposition
qc.h(0)
qc.h(1)

# Oracle marks |11>
qc.cz(0, 1)

# Diffuser
qc.h(0)
qc.h(1)
qc.x(0)
qc.x(1)
qc.cz(0, 1)
qc.x(0)
qc.x(1)
qc.h(0)
qc.h(1)

qc.measure(0, 0)
qc.measure(1, 1)
'''
_add("templates/grover_search_qiskit", "qiskit", "frontend/lib/fileTemplates.ts", GROVER_QISKIT_TEMPLATE, {"11": 1.0})

_add("templates/qft_qiskit", "qiskit", "frontend/lib/fileTemplates.ts", '''from qiskit import QuantumCircuit
import numpy as np

qc = QuantumCircuit(3, 3)

# Put input in a simple basis/superposition
qc.x(0)

# QFT on 3 qubits
qc.h(2)
qc.cp(np.pi / 2, 1, 2)
qc.cp(np.pi / 4, 0, 2)

qc.h(1)
qc.cp(np.pi / 2, 0, 1)

qc.h(0)

# Reverse qubit order
qc.swap(0, 2)

qc.measure(0, 0)
qc.measure(1, 1)
qc.measure(2, 2)
''', uniform(3), "QFT of a basis state: every qubit ends in an equal superposition")

_add("templates/variational_ansatz_pennylane", "pennylane", "frontend/lib/fileTemplates.ts", '''import pennylane as qml
import numpy as np

dev = qml.device('default.qubit', wires=2)

params = np.array([0.3, -0.7, 0.2, 1.1])

@qml.qnode(dev)
def variational_circuit(theta):
    qml.RY(theta[0], wires=0)
    qml.RY(theta[1], wires=1)
    qml.CNOT(wires=[0, 1])
    qml.RZ(theta[2], wires=0)
    qml.RZ(theta[3], wires=1)
    return qml.expval(qml.PauliZ(0))
''', None,
     "qnode is never called, so theta has no value: conversion must fail loudly or declare theta "
     "as an unbound input; it must not silently invent values")

_add("templates/qrng_bit_pennylane", "pennylane", "frontend/lib/fileTemplates.ts", '''import pennylane as qml

dev = qml.device('default.qubit', wires=1, shots=1)

@qml.qnode(dev)
def random_bit():
    qml.Hadamard(wires=0)
    return qml.sample(qml.PauliZ(0))
''', {"0": 0.5, "1": 0.5})

# examples/page.tsx (non-hybrid) ----------------------------------------------
_add("examples/teleportation-cirq", "cirq", "frontend/app/examples/page.tsx", '''import cirq

# Create 3 qubits: q0 (state to teleport), q1 & q2 (Bell pair)
q0, q1, q2 = cirq.LineQubit.range(3)

# Classical bits placeholder for conditional operations
c = [0, 0, 0]

# Initialize empty circuit
circuit = cirq.Circuit()

# STEP 1: Prepare the state to teleport (|+⟩ state as example)
circuit.append(cirq.H(q0))

# STEP 2: Create Bell pair between q1 and q2 (|00⟩ + |11⟩)/√2
circuit.append(cirq.H(q1))
circuit.append(cirq.CNOT(q1, q2))

# STEP 3: Bell measurement - entangle q0 with the Bell pair
circuit.append(cirq.CNOT(q0, q1))
circuit.append(cirq.H(q0))

# STEP 4: Measure qubits 0 and 1 (Alice's measurements)
circuit.append(cirq.measure(q0, key='c0'))
circuit.append(cirq.measure(q1, key='c1'))

# STEP 5: Apply corrections based on measurement results (Bob's operations)
if c[1] == 1:
    circuit.append(cirq.X(q2))
if c[0] == 1:
    circuit.append(cirq.Z(q2))

# STEP 6: Final measurement to verify teleportation
circuit.append(cirq.measure(q2, key='c2'))''', uniform(3), "teleports |+>, uniform over 8")

_add("examples/teleportation-qiskit", "qiskit", "frontend/app/examples/page.tsx",
     TELEPORT_QISKIT.rstrip("\n"), uniform(3), "teleports |+>, uniform over 8")

_add("examples/teleportation-pennylane", "pennylane", "frontend/app/examples/page.tsx", '''import pennylane as qml

# Define quantum device with 3 wires (qubits)
dev = qml.device("default.qubit", wires=3)

# Classical bits placeholder for conditional operations
c = [0, 0, 0]

@qml.qnode(dev)
def teleportation_circuit():
    # STEP 1: Prepare the state to teleport
    qml.Hadamard(wires=0)

    # STEP 2: Create Bell pair between wires 1 and 2
    qml.Hadamard(wires=1)
    qml.CNOT(wires=[1, 2])

    # STEP 3: Bell measurement
    qml.CNOT(wires=[0, 1])
    qml.Hadamard(wires=0)

    # STEP 4: Measure qubits 0 and 1
    qml.measure(wires=0)
    qml.measure(wires=1)

    # STEP 5: Conditional corrections
    if c[1] == 1:
        qml.PauliX(wires=2)
    if c[0] == 1:
        qml.PauliZ(wires=2)

    # STEP 6: Final measurement
    qml.measure(wires=2)''', uniform(3), "teleports |+>, uniform over 8")

_add("examples/deutsch-jozsa-pennylane", "pennylane", "frontend/app/examples/page.tsx", '''import pennylane as qml

# 3 qubits: 2 input qubits + 1 ancilla qubit
dev = qml.device("default.qubit", wires=3)

@qml.qnode(dev)
def deutsch_jozsa_circuit():
    # STEP 1: Initialize ancilla qubit to |1⟩
    qml.PauliX(wires=2)

    # STEP 2: Apply Hadamard to ALL qubits (create superposition)
    for i in range(3):
        qml.Hadamard(wires=i)

    # STEP 3: Oracle - implements a BALANCED function
    # This oracle flips ancilla when input qubits differ
    qml.CNOT(wires=[0, 2])
    qml.CNOT(wires=[1, 2])

    # STEP 4: Apply Hadamard to INPUT qubits only (not ancilla)
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)

    # STEP 5: Measure input qubits
    # Result ≠ |00⟩ means BALANCED function
    qml.measure(wires=0)
    qml.measure(wires=1)''', {"11": 1.0})

_add("examples/deutsch-jozsa-cirq", "cirq", "frontend/app/examples/page.tsx", '''import cirq

# Create 3 qubits
q0, q1, q2 = cirq.LineQubit.range(3)

# Classical bits placeholder
c = [0, 0]

circuit = cirq.Circuit()

# STEP 1: Initialize ancilla to |1⟩
circuit.append(cirq.X(q2))

# STEP 2: Hadamard on all qubits
for i in range(3):
    circuit.append(cirq.H(cirq.LineQubit(i)))

# STEP 3: Balanced Oracle
circuit.append(cirq.CNOT(q0, q2))
circuit.append(cirq.CNOT(q1, q2))

# STEP 4: Hadamard on input qubits
circuit.append(cirq.H(q0))
circuit.append(cirq.H(q1))

# STEP 5: Measure input qubits
circuit.append(cirq.measure(q0, key='c0'))
circuit.append(cirq.measure(q1, key='c1'))''', {"11": 1.0})

_add("examples/qrng-qiskit", "qiskit", "frontend/app/examples/page.tsx", '''from qiskit import QuantumCircuit, execute, Aer

# Number of random bits to generate
n_bits = 8

# Create circuit with n_bits qubits and classical bits
qc = QuantumCircuit(n_bits, n_bits)

# Put each qubit in superposition (50/50 probability of 0 or 1)
for i in range(n_bits):
    qc.h(i)

# Measure all qubits to collapse superposition into random values
qc.measure(range(n_bits), range(n_bits))''', uniform(8))

_add("examples/qrng-cirq", "cirq", "frontend/app/examples/page.tsx", QRNG_CIRQ.rstrip("\n"), uniform(8))

_add("examples/qrng-pennylane", "pennylane", "frontend/app/examples/page.tsx", '''import pennylane as qml

# Number of random bits to generate
n_bits = 8

# Define device with n_bits wires
dev = qml.device("default.qubit", wires=n_bits)

@qml.qnode(dev)
def qrng_circuit():
    # Put each qubit in superposition
    for i in range(n_bits):
        qml.Hadamard(wires=i)

    # Measure all qubits
    for i in range(n_bits):
        qml.measure(wires=i)''', uniform(8))

_add("examples/grover-qiskit", "qiskit", "frontend/app/examples/page.tsx", '''from qiskit import QuantumCircuit

# 2 qubits = 4 possible states to search
qc = QuantumCircuit(2, 2)

# STEP 1: Initialize superposition (equal probability for all states)
qc.h(0)
qc.h(1)

# STEP 2: Oracle - mark target state |11⟩ with phase flip
# CZ applies -1 phase only when both qubits are |1⟩
qc.cz(0, 1)

# STEP 3: Diffusion Operator (Grover's diffusion)
# Reflects amplitude about the mean, amplifying marked state
qc.h(0)
qc.h(1)
qc.x(0)
qc.x(1)
qc.cz(0, 1)    # Phase flip on |00⟩ (which was |11⟩ before X gates)
qc.x(0)
qc.x(1)
qc.h(0)
qc.h(1)

# STEP 4: Measure - should get |11⟩ with high probability
qc.measure([0, 1], [0, 1])''', {"11": 1.0})

_add("examples/grover-cirq", "cirq", "frontend/app/examples/page.tsx", '''import cirq

# Create 2 qubits
q0, q1 = cirq.LineQubit.range(2)

circuit = cirq.Circuit()

# STEP 1: Initialize superposition
circuit.append(cirq.H(q0))
circuit.append(cirq.H(q1))

# STEP 2: Oracle - mark |11⟩
circuit.append(cirq.CZ(q0, q1))

# STEP 3: Diffusion Operator
circuit.append(cirq.H(q0))
circuit.append(cirq.H(q1))
circuit.append(cirq.X(q0))
circuit.append(cirq.X(q1))
circuit.append(cirq.CZ(q0, q1))
circuit.append(cirq.X(q0))
circuit.append(cirq.X(q1))
circuit.append(cirq.H(q0))
circuit.append(cirq.H(q1))

# STEP 4: Measure
circuit.append(cirq.measure(q0, key='c0'))
circuit.append(cirq.measure(q1, key='c1'))''', {"11": 1.0})

_add("examples/xor-demo-pennylane", "pennylane", "frontend/app/examples/page.tsx",
     XOR_DEMO_PL.rstrip("\n"), {"01": 0.5, "10": 0.5})

_add("examples/qml-xor-classifier", "pennylane", "frontend/app/examples/page.tsx",
     QML_XOR_PL.rstrip("\n"), _qml_xor_expected())

_add("examples/bell-state-qiskit", "qiskit", "frontend/app/examples/page.tsx", '''from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

# Create quantum and classical registers
qr = QuantumRegister(2, 'q')
cr = ClassicalRegister(2, 'c')

# Create quantum circuit
qc = QuantumCircuit(qr, cr)

# Apply Hadamard gate to first qubit
qc.h(qr[0])

# Apply CNOT gate between qubits 0 and 1
qc.cx(qr[0], qr[1])

# Measure both qubits
qc.measure(qr, cr)

print("Bell State Circuit (Qiskit):")
print(qc)''', BELL)

_add("examples/bell-state-cirq", "cirq", "frontend/app/examples/page.tsx", '''import cirq

# Create qubits
q0, q1 = cirq.LineQubit.range(2)

# Create Bell state circuit
circuit = cirq.Circuit(
    cirq.H(q0),           # Hadamard on first qubit
    cirq.CNOT(q0, q1),    # CNOT with q0 as control
    cirq.measure(q0, q1)  # Measure both qubits
)

print("Bell State Circuit (Cirq):")
print(circuit)''', BELL)

_add("examples/bell-state-pennylane", "pennylane", "frontend/app/examples/page.tsx", '''import pennylane as qml

dev = qml.device("default.qubit", wires=2)

@qml.qnode(dev)
def bell_state_circuit():
    qml.Hadamard(wires=0)
    qml.CNOT(wires=[0, 1])
    return qml.expval(qml.PauliZ(0)), qml.expval(qml.PauliZ(1))

# Execute circuit
result = bell_state_circuit()
print("Bell State Circuit (PennyLane):")
print(f"Expectation values: {result}")''', BELL, "no measurement: backend samples all qubits")

_add("examples/ghz-state-qiskit", "qiskit", "frontend/app/examples/page.tsx", '''from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

def create_ghz_circuit(n_qubits):
    qr = QuantumRegister(n_qubits, 'q')
    cr = ClassicalRegister(n_qubits, 'c')
    qc = QuantumCircuit(qr, cr)

    # Apply Hadamard to first qubit
    qc.h(qr[0])

    # Apply CNOT gates to create entanglement
    for i in range(1, n_qubits):
        qc.cx(qr[0], qr[i])

    # Measure all qubits
    qc.measure(qr, cr)

    return qc

# Create 4-qubit GHZ state
ghz_circuit = create_ghz_circuit(4)
print("GHZ State Circuit (4 qubits):")
print(ghz_circuit)''', {"0000": 0.5, "1111": 0.5})

_add("examples/quantum-fourier-transform", "qiskit", "frontend/app/examples/page.tsx", '''from qiskit import QuantumCircuit
import numpy as np

def create_qft_circuit(n_qubits):
    qc = QuantumCircuit(n_qubits)

    for i in range(n_qubits):
        qc.h(i)

        for j in range(i + 1, n_qubits):
            angle = 2 * np.pi / (2 ** (j - i + 1))
            qc.cp(angle, j, i)

    # Swap qubits to get correct order
    for i in range(n_qubits // 2):
        qc.swap(i, n_qubits - 1 - i)

    return qc

# Create 4-qubit QFT
qft_circuit = create_qft_circuit(4)
print("Quantum Fourier Transform (4 qubits):")
print(qft_circuit)''', uniform(4), "QFT of |0000> is the uniform superposition; no measurement -> all qubits sampled")

_add("examples/quantum-neural-network", "pennylane", "frontend/app/examples/page.tsx", '''import pennylane as qml
import numpy as np

def create_quantum_neural_network(n_qubits=2, n_layers=2):
    dev = qml.device("default.qubit", wires=n_qubits)

    @qml.qnode(dev)
    def quantum_neural_network(inputs, weights):
        # Encode input data
        for i in range(n_qubits):
            qml.RX(inputs[i], wires=i)
            qml.RY(inputs[i], wires=i)

        # Process through layers
        for layer in range(n_layers):
            # Entangling layer
            for i in range(n_qubits - 1):
                qml.CNOT(wires=[i, i + 1])

            # Rotation layer
            for i in range(n_qubits):
                qml.RX(weights[layer, i, 0], wires=i)
                qml.RY(weights[layer, i, 1], wires=i)
                qml.RZ(weights[layer, i, 2], wires=i)

        # Measure in computational basis
        return [qml.expval(qml.PauliZ(i)) for i in range(n_qubits)]

    return quantum_neural_network

# Create quantum neural network
qnn = create_quantum_neural_network(2, 2)

# Initialize parameters
inputs = np.random.randn(2)
weights = np.random.randn(2, 2, 3)

# Execute circuit
result = qnn(inputs, weights)
print("Quantum Neural Network:")
print(f"Input: {inputs}")
print(f"Weights shape: {weights.shape}")
print(f"Output: {result}")''', None,
     "inputs/weights are np.random at run time, so there is no fixed expected distribution")

_add("examples/error-correction", "qiskit", "frontend/app/examples/page.tsx", '''from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

def create_error_correction_circuit():
    # Create quantum and classical registers
    qr = QuantumRegister(5, 'q')  # 3 data qubits + 2 ancilla qubits
    cr = ClassicalRegister(3, 'c')  # Measure only data qubits

    # Create quantum circuit
    qc = QuantumCircuit(qr, cr)

    # Encoding: Prepare logical |1⟩ state
    qc.x(qr[0])  # Flip first qubit to |1⟩

    # Apply CNOT gates to create encoded state
    qc.cx(qr[0], qr[1])
    qc.cx(qr[0], qr[2])

    # Error detection: Apply syndrome measurement
    qc.cx(qr[0], qr[3])
    qc.cx(qr[1], qr[3])
    qc.cx(qr[1], qr[4])
    qc.cx(qr[2], qr[4])

    # Measure ancilla qubits (syndrome)
    qc.measure(qr[3], cr[0])
    qc.measure(qr[4], cr[1])

    # Measure data qubits
    qc.measure(qr[0], cr[2])

    return qc

error_correction_circuit = create_error_correction_circuit()
print("3-Qubit Bit-Flip Error Correction Circuit:")
print(error_correction_circuit)''', {"001": 1.0}, "data |111>, syndromes 0,0 -> c=(0,0,1)")


# ---------------------------------------------------------------------------
# Extra textbook circuits (all three frameworks)
# ---------------------------------------------------------------------------

_add("extra/ghz3-qiskit", "qiskit", "extra", '''from qiskit import QuantumCircuit
qc = QuantumCircuit(3, 3)
qc.h(0)
qc.cx(0, 1)
qc.cx(1, 2)
qc.measure([0, 1, 2], [0, 1, 2])
''', {"000": 0.5, "111": 0.5})

_add("extra/ghz3-cirq", "cirq", "extra", '''import cirq
q = cirq.LineQubit.range(3)
circuit = cirq.Circuit()
circuit.append(cirq.H(q[0]))
circuit.append(cirq.CNOT(q[0], q[1]))
circuit.append(cirq.CNOT(q[1], q[2]))
circuit.append(cirq.measure(*q, key='m'))
''', {"000": 0.5, "111": 0.5})

_add("extra/ghz3-pennylane", "pennylane", "extra", '''import pennylane as qml
dev = qml.device("default.qubit", wires=3)

@qml.qnode(dev)
def ghz():
    qml.Hadamard(wires=0)
    qml.CNOT(wires=[0, 1])
    qml.CNOT(wires=[1, 2])
    return qml.probs(wires=[0, 1, 2])
''', {"000": 0.5, "111": 0.5})

# Bernstein-Vazirani, secret s = 101 (q0=1, q1=0, q2=1), ancilla q3.
_add("extra/bv101-qiskit", "qiskit", "extra", '''from qiskit import QuantumCircuit
qc = QuantumCircuit(4, 3)
qc.x(3)
qc.h(3)
for i in range(3):
    qc.h(i)
qc.cx(0, 3)
qc.cx(2, 3)
for i in range(3):
    qc.h(i)
for i in range(3):
    qc.measure(i, i)
''', {"101": 1.0})

_add("extra/bv101-cirq", "cirq", "extra", '''import cirq
q0, q1, q2, anc = cirq.LineQubit.range(4)
circuit = cirq.Circuit(
    cirq.X(anc), cirq.H(anc),
    cirq.H(q0), cirq.H(q1), cirq.H(q2),
    cirq.CNOT(q0, anc), cirq.CNOT(q2, anc),
    cirq.H(q0), cirq.H(q1), cirq.H(q2),
    cirq.measure(q0, q1, q2, key='s'),
)
''', {"101": 1.0})

_add("extra/bv101-pennylane", "pennylane", "extra", '''import pennylane as qml
dev = qml.device("default.qubit", wires=4)

@qml.qnode(dev)
def bv():
    qml.PauliX(wires=3)
    qml.Hadamard(wires=3)
    for i in range(3):
        qml.Hadamard(wires=i)
    qml.CNOT(wires=[0, 3])
    qml.CNOT(wires=[2, 3])
    for i in range(3):
        qml.Hadamard(wires=i)
    return qml.probs(wires=[0, 1, 2])
''', {"101": 1.0})

# Deutsch-Jozsa with a CONSTANT oracle (f(x)=1): inputs always measure 00.
_add("extra/dj-constant-qiskit", "qiskit", "extra", '''from qiskit import QuantumCircuit
qc = QuantumCircuit(3, 2)
qc.x(2)
qc.h(0)
qc.h(1)
qc.h(2)
qc.x(2)
qc.h(0)
qc.h(1)
qc.measure(0, 0)
qc.measure(1, 1)
''', {"00": 1.0})

_add("extra/dj-constant-cirq", "cirq", "extra", '''import cirq
q0, q1, q2 = cirq.LineQubit.range(3)
circuit = cirq.Circuit()
circuit.append(cirq.X(q2))
circuit.append([cirq.H(q0), cirq.H(q1), cirq.H(q2)])
circuit.append(cirq.X(q2))
circuit.append([cirq.H(q0), cirq.H(q1)])
circuit.append(cirq.measure(q0, q1, key='m'))
''', {"00": 1.0})

_add("extra/dj-constant-pennylane", "pennylane", "extra", '''import pennylane as qml
dev = qml.device("default.qubit", wires=3)

@qml.qnode(dev)
def dj():
    qml.PauliX(wires=2)
    for i in range(3):
        qml.Hadamard(wires=i)
    qml.PauliX(wires=2)
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    qml.measure(wires=0)
    qml.measure(wires=1)
''', {"00": 1.0})

# Parameterized rotation: ry(pi/3)|0> -> P(1) = sin^2(pi/6) = 0.25
RY_EXPECTED = {"0": 0.75, "1": 0.25}
_add("extra/ry-pi3-qiskit", "qiskit", "extra", '''from qiskit import QuantumCircuit
import numpy as np
qc = QuantumCircuit(1, 1)
qc.ry(np.pi / 3, 0)
qc.measure(0, 0)
''', RY_EXPECTED)

_add("extra/ry-pi3-cirq", "cirq", "extra", '''import cirq
import numpy as np
q = cirq.LineQubit(0)
circuit = cirq.Circuit()
circuit.append(cirq.ry(np.pi / 3)(q))
circuit.append(cirq.measure(q, key='m'))
''', RY_EXPECTED)

_add("extra/ry-pi3-pennylane", "pennylane", "extra", '''import pennylane as qml
import numpy as np
dev = qml.device("default.qubit", wires=1)

@qml.qnode(dev)
def rot():
    qml.RY(np.pi / 3, wires=0)
    return qml.sample(wires=0)
''', RY_EXPECTED)

# PennyLane Rot(phi, theta, omega) = RZ(omega) RY(theta) RZ(phi); on |0> P(1) = sin^2(theta/2)
_add("extra/rot-pennylane", "pennylane", "extra", '''import pennylane as qml
import numpy as np
dev = qml.device("default.qubit", wires=1)

@qml.qnode(dev)
def rot():
    qml.Hadamard(wires=0)
    qml.Rot(np.pi / 2, np.pi / 3, 0.4, wires=0)
    qml.Hadamard(wires=0)
    return qml.probs(wires=0)
''', None, "checked against PennyLane's own simulator in the test")

# Teleportation of |1> WITH real feed-forward: q2 must always read 1.
TELEPORT_ONE = {"001": 0.25, "011": 0.25, "101": 0.25, "111": 0.25}
_add("extra/teleport-one-qiskit", "qiskit", "extra", '''from qiskit import QuantumCircuit
qc = QuantumCircuit(3, 3)
qc.x(0)
qc.h(1)
qc.cx(1, 2)
qc.cx(0, 1)
qc.h(0)
qc.measure(0, 0)
qc.measure(1, 1)
with qc.if_test((qc.clbits[1], 1)):
    qc.x(2)
with qc.if_test((qc.clbits[0], 1)):
    qc.z(2)
qc.measure(2, 2)
''', TELEPORT_ONE)

_add("extra/teleport-one-cirq", "cirq", "extra", '''import cirq
q0, q1, q2 = cirq.LineQubit.range(3)
circuit = cirq.Circuit(
    cirq.X(q0),
    cirq.H(q1),
    cirq.CNOT(q1, q2),
    cirq.CNOT(q0, q1),
    cirq.H(q0),
    cirq.measure(q0, key='m0'),
    cirq.measure(q1, key='m1'),
    cirq.X(q2).with_classical_controls('m1'),
    cirq.Z(q2).with_classical_controls('m0'),
    cirq.measure(q2, key='m2'),
)
''', TELEPORT_ONE)

_add("extra/teleport-one-pennylane", "pennylane", "extra", '''import pennylane as qml
dev = qml.device("default.qubit", wires=3)

@qml.qnode(dev)
def teleport():
    qml.PauliX(wires=0)
    qml.Hadamard(wires=1)
    qml.CNOT(wires=[1, 2])
    qml.CNOT(wires=[0, 1])
    qml.Hadamard(wires=0)
    m0 = qml.measure(wires=0)
    m1 = qml.measure(wires=1)
    qml.cond(m1, qml.PauliX)(wires=2)
    qml.cond(m0, qml.PauliZ)(wires=2)
    qml.measure(wires=2)
''', TELEPORT_ONE)


PROGRAMS_BY_ID = {p["id"]: p for p in PROGRAMS}
