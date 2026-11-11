'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import Image from 'next/image'
import { useRouter } from 'next/navigation'
import { Copy, Play, Code } from '@/components/Icons';
import { Share2, Search } from 'lucide-react';
import toast from 'react-hot-toast'
import { useFileStore } from '@/lib/store'
import { sharedApi } from '@/lib/api'
import Navbar from '@/components/Navbar'
import SiteFooter from '@/components/site/SiteFooter'
import CodeSample from '@/components/site/CodeSample'
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

n_qubits = 2
n_layers = 2
dev = qml.device("default.qubit", wires=n_qubits)

# Fixed example parameters (swap in np.random / a training loop to explore)
inputs = np.array([0.5, -0.3])
weights = np.array([
    [[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
    [[0.7, 0.8, 0.9], [1.0, 1.1, 1.2]],
])

@qml.qnode(dev)
def quantum_neural_network():
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

# Execute circuit
result = quantum_neural_network()
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
        router.push('/app')
      } else {
        toast('Please sign in to try this example in the editor')
        router.push('/login')
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

  const copyToClipboard = (code: string) => {
    navigator.clipboard.writeText(code)
    toast.success('Code copied')
  }

  const frameworkDot = (framework: string) => {
    switch (framework) {
      case 'qiskit': return 'bg-qc-qiskit'
      case 'cirq': return 'bg-qc-cirq'
      case 'pennylane': return 'bg-qc-pennylane'
      default: return 'bg-qc-subtle'
    }
  }

  const label = (value: string) =>
    value === 'pennylane' ? 'PennyLane' : value.charAt(0).toUpperCase() + value.slice(1)

  const selectClass = 'qc-input qc-select'

  return (
    <div className="qc-page">
      <Navbar />

      <main id="main" className="qc-container pb-24 pt-28">
        <header className="flex flex-wrap items-end justify-between gap-6 border-b border-qc-line pb-10">
          <div className="max-w-2xl">
            <p className="qc-eyebrow">Examples</p>
            <h1 className="mt-3 font-display text-display-1 font-semibold text-qc-fg">
              Circuits you can run
            </h1>
            <p className="mt-4 text-lg leading-relaxed text-qc-muted">
              Working programs in Cirq, Qiskit and PennyLane, from a first Bell
              state to Grover&apos;s search. Open one in the editor or copy the
              code.
            </p>
          </div>

          <div
            role="tablist"
            aria-label="Example source"
            className="inline-flex rounded-lg border border-qc-line bg-qc-surface p-1"
          >
            {(['official', 'community'] as const).map((tab) => (
              <button
                key={tab}
                type="button"
                role="tab"
                aria-selected={activeTab === tab}
                onClick={() => setActiveTab(tab)}
                className={`qc-focus flex items-center gap-2 rounded-md px-3.5 py-1.5 text-sm transition-colors duration-150 ${
                  activeTab === tab
                    ? 'bg-qc-surface-3 text-qc-fg'
                    : 'text-qc-muted hover:text-qc-fg'
                }`}
              >
                {tab === 'official' ? (
                  <Code className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <Share2 className="h-4 w-4" aria-hidden="true" />
                )}
                {tab === 'official' ? 'Official' : 'Community'}
              </button>
            ))}
          </div>
        </header>

        {/* Filters */}
        <div className="mt-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-[minmax(0,2fr)_repeat(3,minmax(0,1fr))]">
          <div className="relative sm:col-span-2 lg:col-span-1">
            <label htmlFor="search-input" className="sr-only">Search examples</label>
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-qc-subtle" aria-hidden="true" />
            <input
              id="search-input"
              type="search"
              placeholder="Search by name, algorithm or tag"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="qc-input !pl-9"
            />
          </div>

          <div>
            <label htmlFor="category-select" className="sr-only">Category</label>
            <select
              id="category-select"
              value={selectedCategory}
              onChange={(e) => setSelectedCategory(e.target.value)}
              className={selectClass}
            >
              <option value="all">All categories</option>
              {categories.map(category => (
                <option key={category} value={category}>{category}</option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="framework-select" className="sr-only">Framework</label>
            <select
              id="framework-select"
              value={selectedFramework}
              onChange={(e) => setSelectedFramework(e.target.value)}
              className={selectClass}
            >
              <option value="all">All frameworks</option>
              {frameworks.map(framework => (
                <option key={framework} value={framework}>{label(framework)}</option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="difficulty-select" className="sr-only">Difficulty</label>
            <select
              id="difficulty-select"
              value={selectedDifficulty}
              onChange={(e) => setSelectedDifficulty(e.target.value)}
              className={selectClass}
            >
              <option value="all">All levels</option>
              {difficulties.map(difficulty => (
                <option key={difficulty} value={difficulty}>{label(difficulty)}</option>
              ))}
            </select>
          </div>
        </div>

        <p className="mt-4 text-sm text-qc-subtle" aria-live="polite">
          {activeTab === 'community' && isLoadingCommunity
            ? 'Loading community projects…'
            : `${filteredExamples.length} ${filteredExamples.length === 1 ? 'example' : 'examples'}`}
        </p>

        {/* Grid */}
        <ul className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
          {filteredExamples.map((example) => (
            <li
              key={example.id}
              className="qc-card flex min-w-0 flex-col overflow-hidden transition-colors duration-150 hover:border-qc-line-strong"
            >
              <div className="flex flex-1 flex-col p-5">
                <h2 className="text-[17px] font-semibold leading-snug text-qc-fg">{example.title}</h2>
                {'author' in example && (
                  <p className="mt-1 text-xs text-qc-subtle">
                    Shared by {(example as CommunityExample).author}
                  </p>
                )}
                <p className="mt-2 text-sm leading-relaxed text-qc-muted">{example.description}</p>

                <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-1 pt-4 text-xs text-qc-muted">
                  <span className="inline-flex items-center gap-1.5">
                    <span className={`h-1.5 w-1.5 rounded-full ${frameworkDot(example.framework)}`} aria-hidden="true" />
                    {label(example.framework)}
                  </span>
                  <span aria-hidden="true" className="text-qc-line-strong">/</span>
                  <span>{label(example.difficulty)}</span>
                  {example.tags.slice(0, 2).map(tag => (
                    <span key={tag} className="font-mono text-[11px] text-qc-subtle">#{tag}</span>
                  ))}
                </div>
              </div>

              <CodeSample
                code={example.code.split('\n').slice(0, 8).join('\n')}
                className="max-h-36 !overflow-hidden border-y border-qc-line px-5 py-4 !text-[11.5px] !leading-[1.65] [mask-image:linear-gradient(to_bottom,black_55%,transparent)]"
              />

              <div className="flex items-center gap-2 p-3">
                <button
                  type="button"
                  onClick={() => openInEditor(example)}
                  className="qc-btn qc-btn-primary qc-btn-sm"
                >
                  <Play className="h-3.5 w-3.5" aria-hidden="true" />
                  Open in editor
                </button>
                <button
                  type="button"
                  onClick={() => copyToClipboard(example.code)}
                  className="qc-btn qc-btn-quiet qc-btn-sm"
                >
                  <Copy className="h-3.5 w-3.5" aria-hidden="true" />
                  Copy
                </button>
              </div>
            </li>
          ))}
        </ul>

        {activeTab === 'community' && isLoadingCommunity ? (
          <div className="flex items-center justify-center gap-3 py-20 text-sm text-qc-muted" role="status">
            <span className="h-4 w-4 animate-spin rounded-full border-2 border-qc-line-strong border-t-qc-accent" aria-hidden="true" />
            Loading community projects…
          </div>
        ) : filteredExamples.length === 0 ? (
          <div className="mt-4 rounded-xl border border-dashed border-qc-line-strong px-6 py-16 text-center">
            <h2 className="font-medium text-qc-fg">
              {activeTab === 'community' ? 'No community projects yet' : 'No examples match these filters'}
            </h2>
            <p className="mx-auto mt-2 max-w-md text-sm text-qc-muted">
              {activeTab === 'community'
                ? 'Open the editor and use Share to publish a circuit here.'
                : 'Clear the search or pick a different framework or level.'}
            </p>
          </div>
        ) : null}
      </main>

      <SiteFooter />
    </div>
  )
}
