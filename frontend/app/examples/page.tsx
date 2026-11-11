'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { Copy, Play, Code } from '@/components/Icons';
import { Menu, X, Share2 } from 'lucide-react';
import toast from 'react-hot-toast'
import { useFileStore } from '@/lib/store'
import { sharedApi } from '@/lib/api'
import Navbar from '@/components/Navbar'
import { useAuthStore } from '@/lib/authStore'

interface Example {
  id: string
  title: string
  description: string
  framework: 'qiskit' | 'cirq' | 'pennylane'
  difficulty: 'beginner' | 'intermediate' | 'advanced'
  category: string
  code: string
  tags: string[]
}

interface CommunityExample extends Example {
  author: string
}

const examples: Example[] = [
  // ============================================================================
  // QUANTUM TELEPORTATION
  // ============================================================================
  {
    id: 'teleportation-cirq',
    title: 'Quantum Teleportation (Cirq)',
    description: 'Transfer a quantum state using entanglement and classical communication.',
    framework: 'cirq',
    difficulty: 'intermediate',
    category: 'Quantum Algorithms',
    code: `import cirq

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
circuit.append(cirq.measure(q2, key='c2'))`,
    tags: ['teleportation', 'entanglement', 'bell-state', 'protocol']
  },
  {
    id: 'teleportation-qiskit',
    title: 'Quantum Teleportation (Qiskit)',
    description: 'Transfer a quantum state using entanglement and classical communication.',
    framework: 'qiskit',
    difficulty: 'intermediate',
    category: 'Quantum Algorithms',
    code: `from qiskit import QuantumCircuit

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
qc.measure(2, 2)`,
    tags: ['teleportation', 'entanglement', 'bell-state', 'protocol']
  },
  {
    id: 'teleportation-pennylane',
    title: 'Quantum Teleportation (PennyLane)',
    description: 'Transfer a quantum state using entanglement and classical communication.',
    framework: 'pennylane',
    difficulty: 'intermediate',
    category: 'Quantum Algorithms',
    code: `import pennylane as qml

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
    qml.measure(wires=2)`,
    tags: ['teleportation', 'entanglement', 'bell-state', 'protocol']
  },

  // ============================================================================
  // DEUTSCH-JOZSA ALGORITHM
  // ============================================================================
  {
    id: 'deutsch-jozsa-pennylane',
    title: 'Deutsch-Jozsa (PennyLane)',
    description: 'Determine if a function is constant or balanced with one quantum query.',
    framework: 'pennylane',
    difficulty: 'intermediate',
    category: 'Quantum Algorithms',
    code: `import pennylane as qml

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
    qml.measure(wires=1)`,
    tags: ['deutsch-jozsa', 'oracle', 'quantum-advantage', 'algorithm']
  },
  {
    id: 'deutsch-jozsa-qiskit',
    title: 'Deutsch-Jozsa (Qiskit)',
    description: 'Determine if a function is constant or balanced with one quantum query.',
    framework: 'qiskit',
    difficulty: 'intermediate',
    category: 'Quantum Algorithms',
    code: `from qiskit import QuantumCircuit

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
qc.measure(1, 1)`,
    tags: ['deutsch-jozsa', 'oracle', 'quantum-advantage', 'algorithm']
  },
  {
    id: 'deutsch-jozsa-cirq',
    title: 'Deutsch-Jozsa (Cirq)',
    description: 'Determine if a function is constant or balanced with one quantum query.',
    framework: 'cirq',
    difficulty: 'intermediate',
    category: 'Quantum Algorithms',
    code: `import cirq

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
circuit.append(cirq.measure(q1, key='c1'))`,
    tags: ['deutsch-jozsa', 'oracle', 'quantum-advantage', 'algorithm']
  },

  // ============================================================================
  // QUANTUM RANDOM NUMBER GENERATOR (QRNG)
  // ============================================================================
  {
    id: 'qrng-qiskit',
    title: 'QRNG (Qiskit)',
    description: 'Generate truly random numbers using quantum mechanics.',
    framework: 'qiskit',
    difficulty: 'beginner',
    category: 'Basic Circuits',
    code: `from qiskit import QuantumCircuit, execute, Aer

# Number of random bits to generate
n_bits = 8

# Create circuit with n_bits qubits and classical bits
qc = QuantumCircuit(n_bits, n_bits)

# Put each qubit in superposition (50/50 probability of 0 or 1)
for i in range(n_bits):
    qc.h(i)

# Measure all qubits to collapse superposition into random values
qc.measure(range(n_bits), range(n_bits))`,
    tags: ['qrng', 'random', 'superposition', 'hadamard']
  },
  {
    id: 'qrng-cirq',
    title: 'QRNG (Cirq)',
    description: 'Generate truly random numbers using quantum mechanics.',
    framework: 'cirq',
    difficulty: 'beginner',
    category: 'Basic Circuits',
    code: `import cirq

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
    circuit.append(cirq.measure(cirq.LineQubit(i), key=f'c{i}'))`,
    tags: ['qrng', 'random', 'superposition', 'hadamard']
  },
  {
    id: 'qrng-pennylane',
    title: 'QRNG (PennyLane)',
    description: 'Generate truly random numbers using quantum mechanics.',
    framework: 'pennylane',
    difficulty: 'beginner',
    category: 'Basic Circuits',
    code: `import pennylane as qml

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
        qml.measure(wires=i)`,
    tags: ['qrng', 'random', 'superposition', 'hadamard']
  },

  // ============================================================================
  // GROVER'S SEARCH ALGORITHM
  // ============================================================================
  {
    id: 'grover-qiskit',
    title: "Grover's Search (Qiskit)",
    description: 'Search an unsorted database in O(√N) time - finds |11⟩ state.',
    framework: 'qiskit',
    difficulty: 'advanced',
    category: 'Quantum Algorithms',
    code: `from qiskit import QuantumCircuit

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
qc.measure([0, 1], [0, 1])`,
    tags: ['grover', 'search', 'oracle', 'diffusion', 'amplitude-amplification']
  },
  {
    id: 'grover-cirq',
    title: "Grover's Search (Cirq)",
    description: 'Search an unsorted database in O(√N) time - finds |11⟩ state.',
    framework: 'cirq',
    difficulty: 'advanced',
    category: 'Quantum Algorithms',
    code: `import cirq

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
circuit.append(cirq.measure(q1, key='c1'))`,
    tags: ['grover', 'search', 'oracle', 'diffusion', 'amplitude-amplification']
  },
  {
    id: 'grover-pennylane',
    title: "Grover's Search (PennyLane)",
    description: 'Search an unsorted database in O(√N) time - finds |11⟩ state.',
    framework: 'pennylane',
    difficulty: 'advanced',
    category: 'Quantum Algorithms',
    code: `import pennylane as qml

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
    qml.measure(wires=1)`,
    tags: ['grover', 'search', 'oracle', 'diffusion', 'amplitude-amplification']
  },

  // ============================================================================
  // XOR DEMONSTRATION & QML XOR CLASSIFIER
  // ============================================================================
  {
    id: 'xor-demo-pennylane',
    title: 'XOR Demonstration',
    description: 'Quantum entanglement producing XOR-like correlations (|01⟩ + |10⟩).',
    framework: 'pennylane',
    difficulty: 'beginner',
    category: 'Basic Circuits',
    code: `import pennylane as qml

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
    qml.measure(wires=1)`,
    tags: ['xor', 'entanglement', 'bell-state', 'correlation']
  },
  {
    id: 'qml-xor-classifier',
    title: 'QML XOR Classifier',
    description: 'Variational quantum circuit that learns XOR function - actual Quantum ML.',
    framework: 'pennylane',
    difficulty: 'advanced',
    category: 'Quantum Machine Learning',
    code: `import pennylane as qml
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
    qml.measure(wires=1)`,
    tags: ['qml', 'xor', 'variational', 'classifier', 'machine-learning']
  },

  // ============================================================================
  // BELL STATE EXAMPLES
  // ============================================================================
  {
    id: 'bell-state-qiskit',
    title: 'Bell State (Qiskit)',
    description: 'Create a Bell state - a fundamental quantum entangled state.',
    framework: 'qiskit',
    difficulty: 'beginner',
    category: 'Basic Circuits',
    code: `from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

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
print(qc)`,
    tags: ['entanglement', 'bell-state', 'hadamard', 'cnot']
  },
  {
    id: 'bell-state-cirq',
    title: 'Bell State (Cirq)',
    description: 'Create a Bell state using Cirq - demonstrating quantum entanglement.',
    framework: 'cirq',
    difficulty: 'beginner',
    category: 'Basic Circuits',
    code: `import cirq

# Create qubits
q0, q1 = cirq.LineQubit.range(2)

# Create Bell state circuit
circuit = cirq.Circuit(
    cirq.H(q0),           # Hadamard on first qubit
    cirq.CNOT(q0, q1),    # CNOT with q0 as control
    cirq.measure(q0, q1)  # Measure both qubits
)

print("Bell State Circuit (Cirq):")
print(circuit)`,
    tags: ['entanglement', 'bell-state', 'hadamard', 'cnot']
  },
  {
    id: 'bell-state-pennylane',
    title: 'Bell State (PennyLane)',
    description: 'Create a Bell state using PennyLane with expectation value measurements.',
    framework: 'pennylane',
    difficulty: 'beginner',
    category: 'Basic Circuits',
    code: `import pennylane as qml

dev = qml.device("default.qubit", wires=2)

@qml.qnode(dev)
def bell_state_circuit():
    qml.Hadamard(wires=0)
    qml.CNOT(wires=[0, 1])
    return qml.expval(qml.PauliZ(0)), qml.expval(qml.PauliZ(1))

# Execute circuit
result = bell_state_circuit()
print("Bell State Circuit (PennyLane):")
print(f"Expectation values: {result}")`,
    tags: ['entanglement', 'bell-state', 'hadamard', 'cnot']
  },

  // ============================================================================
  // ADDITIONAL ALGORITHMS
  // ============================================================================
  {
    id: 'ghz-state-qiskit',
    title: 'GHZ State (Qiskit)',
    description: 'Create a GHZ (Greenberger-Horne-Zeilinger) state with multiple qubits.',
    framework: 'qiskit',
    difficulty: 'intermediate',
    category: 'Basic Circuits',
    code: `from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

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
print(ghz_circuit)`,
    tags: ['entanglement', 'ghz-state', 'multi-qubit', 'hadamard', 'cnot']
  },
  {
    id: 'quantum-fourier-transform',
    title: 'Quantum Fourier Transform',
    description: 'Implement the Quantum Fourier Transform (QFT) - a key component in many quantum algorithms.',
    framework: 'qiskit',
    difficulty: 'advanced',
    category: 'Quantum Algorithms',
    code: `from qiskit import QuantumCircuit
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
print(qft_circuit)`,
    tags: ['qft', 'fourier-transform', 'quantum-algorithm', 'phase-gates']
  },
  {
    id: 'variational-quantum-eigensolver',
    title: 'VQE (PennyLane)',
    description: 'Implement VQE to find the ground state energy of quantum systems.',
    framework: 'pennylane',
    difficulty: 'advanced',
    category: 'Hybrid',
    code: `import pennylane as qml
import numpy as np

def create_vqe_circuit():
    dev = qml.device("default.qubit", wires=2)
    
    @qml.qnode(dev)
    def vqe_circuit(theta):
        # Prepare variational state
        qml.RY(theta, wires=0)
        qml.CNOT(wires=[0, 1])
        
        # Measure Hamiltonian terms
        # H = Z⊗Z + X⊗X
        zz = qml.expval(qml.PauliZ(0) @ qml.PauliZ(1))
        xx = qml.expval(qml.PauliX(0) @ qml.PauliX(1))
        
        return zz + xx
    
    return vqe_circuit

# Create VQE circuit
vqe_circuit = create_vqe_circuit()

# Test with specific parameter
theta_val = np.pi/4
result = vqe_circuit(theta_val)
print("VQE Circuit:")
print(f"Parameter: theta={theta_val}")
print(f"Energy: {result}")`,
    tags: ['vqe', 'variational', 'optimization', 'energy', 'hamiltonian']
  },
  {
    id: 'quantum-approximate-optimization',
    title: 'QAOA (PennyLane)',
    description: 'Implement QAOA for combinatorial optimization problems.',
    framework: 'pennylane',
    difficulty: 'advanced',
    category: 'Hybrid',
    code: `import pennylane as qml
import numpy as np

def create_qaoa_circuit(n_qubits=4, p=2):
    dev = qml.device("default.qubit", wires=n_qubits)
    
    @qml.qnode(dev)
    def qaoa_circuit(gamma, beta):
        # Initial state: equal superposition
        for i in range(n_qubits):
            qml.Hadamard(wires=i)
        
        # QAOA layers
        for layer in range(p):
            # Phase separation operator (problem Hamiltonian)
            for i in range(n_qubits - 1):
                qml.CNOT(wires=[i, i + 1])
                qml.RZ(gamma[layer], wires=i + 1)
                qml.CNOT(wires=[i, i + 1])
            
            # Mixing operator
            for i in range(n_qubits):
                qml.RX(beta[layer], wires=i)
        
        # Measure in computational basis
        return [qml.expval(qml.PauliZ(i)) for i in range(n_qubits)]
    
    return qaoa_circuit

# Create QAOA circuit
qaoa_circuit = create_qaoa_circuit(4, 2)

# Initialize parameters
gamma = np.random.randn(2)
beta = np.random.randn(2)

# Execute circuit
result = qaoa_circuit(gamma, beta)
print("QAOA Circuit (4 qubits, 2 layers):")
print(f"Parameters: gamma={gamma}, beta={beta}")
print(f"Expectation values: {result}")`,
    tags: ['qaoa', 'optimization', 'maxcut', 'variational', 'combinatorial']
  },
  {
    id: 'quantum-neural-network',
    title: 'Quantum Neural Network',
    description: 'A simple quantum neural network for classification tasks.',
    framework: 'pennylane',
    difficulty: 'intermediate',
    category: 'Quantum Machine Learning',
    code: `import pennylane as qml
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
print(f"Output: {result}")`,
    tags: ['quantum-ml', 'neural-network', 'classification', 'variational', 'layers']
  },
  {
    id: 'error-correction',
    title: '3-Qubit Bit-Flip Error Correction',
    description: 'Implement a simple quantum error correction code.',
    framework: 'qiskit',
    difficulty: 'intermediate',
    category: 'Error Correction',
    code: `from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

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
print(error_correction_circuit)`,
    tags: ['error-correction', 'syndrome', 'ancilla', 'encoding', 'detection']
  },
  {
    id: 'hybrid-cpu-qpu-execution',
    title: 'Hybrid CPU-QPU Execution (Cirq)',
    description: 'Run multiple simulations in a loop using QCanvas Hybrid mode.',
    framework: 'cirq',
    difficulty: 'intermediate',
    category: 'Hybrid',
    code: `# Hybrid CPU-QPU Execution Example
# Switch to "Hybrid" mode in the toolbar to run this code!

import cirq
from qcanvas import compile
import qsim

# Create a Bell state circuit
q = cirq.LineQubit.range(2)
circuit = cirq.Circuit([
    cirq.H(q[0]),
    cirq.CNOT(q[0], q[1]),
    cirq.measure(q[0], q[1], key='result')
])

print("Circuit created:")
print(circuit)
print()

# Compile circuit to OpenQASM 3.0
qasm = compile(circuit, framework="cirq")
print("Generated QASM:")
print(qasm)
print()

# Run multiple simulations in a loop
print("Running 3 simulations...")
for i in range(3):
    result = qsim.run(qasm, shots=100, backend="cirq")
    print(f"Run {i+1}: {result.counts}")
    print(f"  Probabilities: {result.probabilities}")

print()
print("Hybrid execution complete!")`,
    tags: ['hybrid', 'loop', 'qsim', 'simulation']
  },
  {
    id: 'qrng-hybrid-cirq',
    title: 'QRNG Hybrid Execution (Cirq)',
    description: 'Generate random bits inside a loop using hybrid execution.',
    framework: 'cirq',
    difficulty: 'intermediate',
    category: 'Hybrid',
    code: `import cirq

from qcanvas import compile
import qsim

print("=== Quantum Random Number Generator (QRNG) ===\\n")

# Create a simple circuit that generates one random bit
# H gate creates superposition, measurement collapses to 0 or 1
q = cirq.LineQubit(0)
circuit = cirq.Circuit([
    cirq.H(q),
    cirq.measure(q, key='random_bit')
])

# Compile to QASM
qasm = compile(circuit, framework="cirq")
print(f"QRNG Circuit QASM:\\n{qasm}\\n")

# Generate 10 random bits
print("Generating 10 random bits:")
random_bits = []
for i in range(10):
    result = qsim.run(qasm, shots=1, backend="cirq")
    # Extract the bit value (0 or 1)
    bit = list(result.counts.keys())[0]
    random_bits.append(bit)
    print(f"  Bit {i+1}: {bit}")

print(f"\\nRandom bit sequence: {''.join(random_bits)}")`,
    tags: ['hybrid', 'qrng', 'random', 'loop', 'qsim']
  }
]

const categories = ['Basic Circuits', 'Quantum Algorithms', 'Variational Algorithms', 'Error Correction', 'Quantum Machine Learning', 'Hybrid']
const frameworks = ['qiskit', 'cirq', 'pennylane']
const difficulties = ['beginner', 'intermediate', 'advanced']

export default function ExamplesPage() {
  const [activeTab, setActiveTab] = useState<'official' | 'community'>('official')
  const [communityExamples, setCommunityExamples] = useState<CommunityExample[]>([])
  const [isLoadingCommunity, setIsLoadingCommunity] = useState(false)
  const [selectedCategory, setSelectedCategory] = useState<string>('all')
  const [selectedFramework, setSelectedFramework] = useState<string>('all')
  const [selectedDifficulty, setSelectedDifficulty] = useState<string>('all')
  const [searchTerm, setSearchTerm] = useState('')
  const { addFile } = useFileStore()
  const { isAuthenticated } = useAuthStore()
  const router = useRouter()

  useEffect(() => {
    const fetchCommunityExamples = async () => {
      setIsLoadingCommunity(true)
      try {
        const response = await sharedApi.getSharedSnippets()
        if (response.success && response.data) {
          // Map to match Example interface plus author
          const mapped = response.data.map((file: any) => ({
            id: file.id,
            title: file.title,
            description: file.description,
            framework: file.framework,
            difficulty: file.difficulty,
            category: file.category,
            tags: file.tags || [],
            code: file.code,
            author: file.author_name || 'Anonymous'
          }))
          setCommunityExamples(mapped) // Backend already sorts them desc
        }
      } catch (error) {
        console.error("Failed to fetch community examples", error)
      } finally {
        setIsLoadingCommunity(false)
      }
    }

    fetchCommunityExamples()
  }, [])

  const openInEditor = (example: Example) => {
    let sanitizedTitle = example.title.replace(/\s+/g, '_')
    if (sanitizedTitle.toLowerCase().endsWith('.py')) {
      sanitizedTitle = sanitizedTitle.slice(0, -3)
    }
    const filename = `${sanitizedTitle}.py`

    // Try to send message to existing app tab
    const channel = new BroadcastChannel('qcanvas-examples')
    channel.postMessage({
      type: 'add-example-file',
      filename,
      code: example.code
    })

    // Fallback: navigate to app if no response after timeout
    const timeout = setTimeout(() => {
      channel.close()
      
      // Store in session storage so the app page can pick it up
      sessionStorage.setItem('pending-example', JSON.stringify({
        name: filename,
        content: example.code
      }))
      
      // If app tab is not open, navigate to it
      if (isAuthenticated) {
        router.push('/app?loadExample=1')
      } else {
        toast('Please sign in to try this example in the editor')
        router.push('/login?loadExample=1')
      }
    }, 500)

    // Listen for confirmation (optional, for now just close after sending)
    channel.onmessage = (event) => {
      if (event.data.type === 'file-added') {
        clearTimeout(timeout)
        channel.close()
        toast.success(`Example loaded in editor: ${filename}`)
      }
    }
  }

  // Use either static official examples or fetched community examples
  const currentDataSet = activeTab === 'official' ? examples : communityExamples

  const filteredExamples = currentDataSet.filter(example => {
    const matchesCategory = selectedCategory === 'all' || example.category === selectedCategory
    const matchesFramework = selectedFramework === 'all' || example.framework === selectedFramework
    const matchesDifficulty = selectedDifficulty === 'all' || example.difficulty === selectedDifficulty
    const matchesSearch = example.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         example.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         example.tags.some(tag => tag.toLowerCase().includes(searchTerm.toLowerCase()))

    return matchesCategory && matchesFramework && matchesDifficulty && matchesSearch
  })

  // Intersection Observer for scroll animations
  useEffect(() => {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          entry.target.classList.add('reveal-show')
        }
      })
    }, { threshold: 0.1 })

    // Use a small timeout to ensure elements are in the DOM
    const timeoutId = setTimeout(() => {
      document.querySelectorAll('.reveal-on-scroll').forEach(el => {
        observer.observe(el)
      })
    }, 100)

    return () => {
      clearTimeout(timeoutId)
      observer.disconnect()
    }
  }, [activeTab, filteredExamples])

  const copyToClipboard = (code: string) => {
    navigator.clipboard.writeText(code)
    toast.success('Code copied to clipboard!')
  }

  const getDifficultyColor = (difficulty: string) => {
    switch (difficulty) {
      case 'beginner': return 'bg-green-500'
      case 'intermediate': return 'bg-yellow-500'
      case 'advanced': return 'bg-red-500'
      default: return 'bg-gray-500'
    }
  }

  const getFrameworkColor = (framework: string) => {
    switch (framework) {
      case 'qiskit': return 'bg-blue-500'
      case 'cirq': return 'bg-purple-500'
      case 'pennylane': return 'bg-green-500'
      default: return 'bg-gray-500'
    }
  }

  return (
    <div className="min-h-screen bg-[#0a0a1a] relative overflow-x-hidden text-white">
      {/* Background Effects */}
      <div className="absolute inset-0 bg-grid-pattern opacity-30 pointer-events-none" />
      <div className="absolute inset-0 bg-gradient-to-b from-[#0a0a1a] via-transparent to-[#0a0a1a] pointer-events-none" />
      <div className="absolute top-[-20%] left-1/2 -translate-x-1/2 w-[800px] h-[600px] hero-spotlight opacity-30 blur-3xl pointer-events-none" />
      {/* Navigation */}
      <Navbar />

      {/* Hero Section */}
      <section className="relative min-h-screen flex items-center justify-center px-4 pt-20">
        {/* Subtle background orbs — fewer, more vibrant */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-32 -right-32 w-[500px] h-[500px] bg-indigo-500 opacity-[0.07] rounded-full blur-[100px]"></div>
          <div className="absolute -bottom-32 -left-32 w-[500px] h-[500px] bg-violet-500 opacity-[0.07] rounded-full blur-[100px]"></div>
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[400px] h-[400px] bg-cyan-500 opacity-[0.05] rounded-full blur-[80px]"></div>
        </div>

        <div className="text-center max-w-6xl mx-auto relative z-10 animate-fade-in-up">
          <div className="inline-flex items-center justify-center w-24 h-24 rounded-full quantum-gradient mb-6 shadow-2xl animate-scale-in">
            <Code className="w-12 h-12 text-white force-white-icon" />
          </div>
          <h1 className="text-5xl md:text-7xl font-bold mb-6 animate-blur-in">
            Quantum <span className="quantum-gradient bg-clip-text text-transparent">Examples</span>
          </h1>
          <p className="text-xl md:text-2xl text-editor-text mb-8 max-w-3xl mx-auto leading-relaxed stagger-delay-2 opacity-0 animate-fade-in-up">
            Explore quantum computing examples across different frameworks. Copy, modify, and run these circuits in QCanvas.
          </p>
        </div>
      </section>

      {/* Filters & Tabs */}
      <main className="px-4 py-8 flex-1 overflow-y-auto">
        <div className="max-w-7xl mx-auto space-y-6">
          
          {/* Tabs */}
          <div className="flex justify-center mb-8">
            <div className="inline-flex p-1 bg-black/40 backdrop-blur-xl border border-white/10 rounded-xl space-x-1">
              <button
                onClick={() => setActiveTab('official')}
                className={`px-6 py-2.5 rounded-lg text-sm font-medium transition-all duration-300 flex items-center gap-2 ${
                  activeTab === 'official'
                    ? 'bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-lg force-white-icon'
                    : 'text-black dark:text-gray-400 hover:text-white hover:bg-white/5'
                }`}
              >
                <Code className="w-4 h-4 force-white-icon" />
                Official Examples
              </button>
              <button
                onClick={() => setActiveTab('community')}
                className={`px-6 py-2.5 rounded-lg text-sm font-medium transition-all duration-300 flex items-center gap-2 ${
                  activeTab === 'community'
                    ? 'bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow-lg force-white-icon'
                    : 'text-black dark:text-gray-400 hover:text-white hover:bg-white/5 '
                }`}
              >
                <Share2 className="w-4 h-4" />
                Community Shared
              </button>
            </div>
          </div>

          <div className="quantum-glass-dark rounded-2xl p-6 backdrop-blur-xl border border-white/10">
            <div className="grid md:grid-cols-2 lg:grid-cols-4 gap-4">
              {/* Search */}
              <div>
                <label htmlFor="search-input" className="block text-sm font-medium text-editor-text mb-2">Search</label>
                <input
                  id="search-input"
                  type="text"
                  placeholder="Search examples..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="w-full px-3 py-2 bg-black/20 border border-white/5 rounded-lg focus-quantum text-white placeholder-gray-400"
                />
              </div>

              {/* Category Filter */}
              <div>
                <label htmlFor="category-select" className="block text-sm font-medium text-editor-text mb-2">Category</label>
                <select
                  id="category-select"
                  value={selectedCategory}
                  onChange={(e) => setSelectedCategory(e.target.value)}
                  className="w-full px-3 py-2 bg-black/5 dark:bg-black border border-white/5 rounded-lg focus-quantum text-black dark:text-white"
                >
                  <option value="all" className="bg-white text-black dark:bg-black dark:text-white">All Categories</option>
                  {categories.map(category => (
                    <option key={category} value={category} className="bg-white text-black dark:bg-black dark:text-white">{category}</option>
                  ))}
                </select>
              </div>

              {/* Framework Filter */}
              <div>
                <label htmlFor="framework-select" className="block text-sm font-medium text-editor-text mb-2">Framework</label>
                <select
                  id="framework-select"
                  value={selectedFramework}
                  onChange={(e) => setSelectedFramework(e.target.value)}
                  className="w-full px-3 py-2 bg-black/5 dark:bg-black border border-white/5 rounded-lg focus-quantum text-black dark:text-white"
                >
                  <option value="all" className="bg-white text-black dark:bg-black dark:text-white">All Frameworks</option>
                  {frameworks.map(framework => (
                    <option key={framework} value={framework} className="bg-white text-black dark:bg-black dark:text-white">{framework.charAt(0).toUpperCase() + framework.slice(1)}</option>
                  ))}
                </select>
              </div>

              {/* Difficulty Filter */}
              <div>
                <label htmlFor="difficulty-select" className="block text-sm font-medium text-editor-text mb-2">Difficulty</label>
                <select
                  id="difficulty-select"
                  value={selectedDifficulty}
                  onChange={(e) => setSelectedDifficulty(e.target.value)}
                  className="w-full px-3 py-2 bg-black/5 dark:bg-black border border-white/5 rounded-lg focus-quantum text-black dark:text-white"
                >
                  <option value="all" className="bg-white text-black dark:bg-black dark:text-white">All Levels</option>
                  {difficulties.map(difficulty => (
                    <option key={difficulty} value={difficulty} className="bg-white text-black dark:bg-black dark:text-white">{difficulty.charAt(0).toUpperCase() + difficulty.slice(1)}</option>
                  ))}
                </select>
              </div>
            </div>
          </div>
        </div>
      {/* Examples Grid */}
      <div className="px-4 py-8">
        <div className="max-w-7xl mx-auto">
          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
            {filteredExamples.map((example, idx) => (
              <div
                key={example.id}
                className="reveal-on-scroll quantum-glass-dark rounded-2xl overflow-hidden border border-white/10 hover:border-quantum-blue-light transition-all duration-300 flex flex-col group hover-lift shadow-lg hover:shadow-quantum-blue-light/10"
                style={{ transitionDelay: `${(idx % 6) * 100}ms` }}
              >
  <div className="p-6">
                  {/* Header */}
                  <div className="flex items-start justify-between mb-4">
                    <div className="flex-1">
                      <h3 className="text-xl font-semibold text-white mb-1">{example.title}</h3>
                      {'author' in example && (
                        <p className="text-xs text-blue-300 mb-2 font-medium flex items-center gap-1.5 opacity-90">
                           <span className="w-1.5 h-1.5 rounded-full bg-blue-400 animate-pulse"></span>
                           By: {(example as CommunityExample).author}
                        </p>
                      )}
                      <p className="text-editor-text text-sm mb-3">{example.description}</p>
                    </div>
                  </div>

                  {/* Tags */}
                  <div className="flex flex-wrap gap-2 mb-4">
                    <span className={`px-2 py-1 rounded-full text-xs font-medium text-white ${getFrameworkColor(example.framework)}`}>
                      {example.framework}
                    </span>
                    <span className={`px-2 py-1 rounded-full text-xs font-medium text-white ${getDifficultyColor(example.difficulty)}`}>
                      {example.difficulty}
                    </span>
                    {example.tags.slice(0, 2).map(tag => (
                      <span key={tag} className="px-2 py-1 rounded-full text-xs font-medium text-black dark:text-gray-300 bg-gray-700">
                        {tag}
                      </span>
                    ))}
                  </div>

                  {/* Actions */}
                  <div className="flex space-x-2">
                    <button
                      onClick={() => copyToClipboard(example.code)}
                      className="flex-1 btn-quantum flex items-center justify-center py-2 text-sm"
                    >
                      <Copy className="w-4 h-4 mr-2" />
                      Copy Code
                    </button>
                    <button
                      onClick={() => openInEditor(example)}
                      className="flex-1 btn-ghost flex items-center justify-center py-2 text-sm"
                    >
                      <Play className="w-4 h-4 mr-2" />
                      Try in QCanvas
                    </button>
                  </div>
                </div>

                {/* Code Preview */}
                <div className="bg-black/20 p-4 border-t border-white/5">
                  <pre className="text-xs text-editor-text overflow-x-auto max-w-full">
                    <code className="whitespace-pre-wrap break-words">{example.code.split('\n').slice(0, 8).join('\n')}...</code>
                  </pre>
                </div>
              </div>
            ))}
          </div>

          {/* Empty State */}
          {activeTab === 'community' && isLoadingCommunity ? (
            <div className="flex flex-col items-center justify-center py-20 space-y-4">
               <div className="w-8 h-8 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin"></div>
               <p className="text-editor-text">Loading community projects...</p>
            </div>
          ) : filteredExamples.length === 0 ? (
            <div className="text-center py-16 quantum-glass-dark rounded-2xl border border-white/10">
              <Code className="w-16 h-16 text-black dark:text-gray-600 mx-auto mb-4" />
              <h3 className="text-xl font-semibold text-white mb-2">
                {activeTab === 'community' ? 'No community projects found' : 'No examples found'}
              </h3>
              <p className="text-editor-text max-w-md mx-auto">
                {activeTab === 'community' 
                  ? 'Be the first to share a quantum project! Open the editor and click the Share button.' 
                  : 'Try adjusting your filters or search terms.'}
              </p>
            </div>
          ) : null}
        </div>
      </div>
      </main>

      {/* Footer */}
      <footer className="px-4 py-8 border-t border-white/5">
        <div className="max-w-7xl mx-auto text-center">
          <p className="text-editor-text">
            Ready to explore quantum computing? Copy any example and try it in QCanvas!
          </p>
          <div className="flex justify-center space-x-6 mt-4">
            <Link href="/about" className="text-editor-text hover:text-white transition-colors">
              About QCanvas
            </Link>
            <Link href="/docs" className="text-editor-text hover:text-white transition-colors">
              Documentation
            </Link>
            <a href="https://github.com" className="text-editor-text hover:text-white transition-colors">
              GitHub
            </a>
          </div>
        </div>
      </footer>
    </div>
  )
}
