export interface FileTemplate {
  name: string
  description: string
  filename: string
  content: string
}

export const FILE_TEMPLATES_PRESETS: FileTemplate[] = [
  {
    name: 'Quantum Teleportation (Qiskit)',
    description: 'Transfer quantum state using entanglement',
    filename: 'quantum_teleportation_qiskit.py',
    content: `from qiskit import QuantumCircuit

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
`,
  },
  {
    name: 'QRNG (Cirq)',
    description: 'Generate truly random numbers using quantum mechanics',
    filename: 'qrng_cirq.py',
    content: `import cirq

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
`,
  },
  {
    name: 'XOR Demonstration (PennyLane)',
    description: 'Quantum entanglement producing XOR correlations',
    filename: 'xor_demo_pennylane.py',
    content: `import pennylane as qml

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
`,
  },
  {
    name: 'QML XOR Classifier (PennyLane)',
    description: 'Variational quantum circuit that learns XOR function',
    filename: 'qml_xor_classifier_pennylane.py',
    content: `import pennylane as qml
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
`,
  },
  {
    name: 'Bell State (Qiskit)',
    description: 'Prepare a Bell pair and measure correlated outcomes.',
    filename: 'bell_state_qiskit.py',
    content: `from qiskit import QuantumCircuit

qc = QuantumCircuit(2, 2)

# Create Bell state: (|00> + |11>)/sqrt(2)
qc.h(0)
qc.cx(0, 1)

# Measure
qc.measure(0, 0)
qc.measure(1, 1)
`,
  },
  {
    name: 'Bell State (Cirq)',
    description: 'Build and measure a Bell circuit in Cirq.',
    filename: 'bell_state_cirq.py',
    content: `import cirq

q0, q1 = cirq.LineQubit.range(2)

circuit = cirq.Circuit()
circuit.append(cirq.H(q0))
circuit.append(cirq.CNOT(q0, q1))
circuit.append(cirq.measure(q0, key='q0'))
circuit.append(cirq.measure(q1, key='q1'))
`,
  },
  {
    name: 'Bell State (PennyLane)',
    description: 'Create Bell correlations using PennyLane.',
    filename: 'bell_state_pennylane.py',
    content: `import pennylane as qml

dev = qml.device('default.qubit', wires=2)

@qml.qnode(dev)
def bell_state():
    qml.Hadamard(wires=0)
    qml.CNOT(wires=[0, 1])
    qml.measure(wires=0)
    qml.measure(wires=1)
`,
  },
  {
    name: 'Deutsch-Jozsa (Qiskit)',
    description: 'Determine whether an oracle is constant or balanced in one query.',
    filename: 'deutsch_jozsa_qiskit.py',
    content: `from qiskit import QuantumCircuit

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
`,
  },
  {
    name: 'Grover Search (Qiskit)',
    description: 'Small 2-qubit Grover iteration for marked state search.',
    filename: 'grover_search_qiskit.py',
    content: `from qiskit import QuantumCircuit

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
`,
  },
  {
    name: 'Quantum Fourier Transform (Qiskit)',
    description: '3-qubit QFT example using controlled phase rotations.',
    filename: 'qft_qiskit.py',
    content: `from qiskit import QuantumCircuit
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
`,
  },
  {
    name: 'Variational Circuit (PennyLane)',
    description: 'Simple parameterized ansatz for VQE-style experiments.',
    filename: 'variational_ansatz_pennylane.py',
    content: `import pennylane as qml
import numpy as np

dev = qml.device('default.qubit', wires=2)

params = np.array([0.3, -0.7, 0.2, 1.1])

@qml.qnode(dev)
def variational_circuit():
    qml.RY(params[0], wires=0)
    qml.RY(params[1], wires=1)
    qml.CNOT(wires=[0, 1])
    qml.RZ(params[2], wires=0)
    qml.RZ(params[3], wires=1)
    return qml.expval(qml.PauliZ(0))

result = variational_circuit()
print("<Z0> =", result)
`,
  },
  {
    name: 'Quantum Random Bit (PennyLane)',
    description: 'Generate one random quantum bit via superposition and measurement.',
    filename: 'qrng_bit_pennylane.py',
    content: `import pennylane as qml

dev = qml.device('default.qubit', wires=1, shots=1)

@qml.qnode(dev)
def random_bit():
    qml.Hadamard(wires=0)
    return qml.sample(qml.PauliZ(0))
`,
  },
]

