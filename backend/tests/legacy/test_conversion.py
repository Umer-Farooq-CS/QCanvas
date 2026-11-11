#!/usr/bin/env python3
"""
Test script to debug conversion issues
"""
import sys
import os

# Add the project root directory to Python path
current_file = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))  # repo root
sys.path.insert(0, project_root)

def test_qiskit_conversion():
    """Test Qiskit to QASM conversion"""
    try:
        from quantum_converters.converters.qiskit_to_qasm import convert_qiskit_to_qasm3
        
        # Test code with proper format
        test_code = '''from qiskit import QuantumCircuit

def get_circuit():
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    return qc'''
        
        print("Testing Qiskit conversion...")
        result = convert_qiskit_to_qasm3(test_code)
        print("✓ Conversion successful!")
        print(f"QASM Code:\n{result.qasm_code}")
        assert result is not None
        
    except Exception as e:
        print(f"✗ Qiskit conversion failed: {e}")
        return False

def test_cirq_conversion():
    """Test Cirq to QASM conversion"""
    try:
        from quantum_converters.converters.cirq_to_qasm import convert_cirq_to_qasm3
        
        # Test code with proper format
        test_code = '''import cirq

def get_circuit():
    q0, q1 = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(
        cirq.H(q0),
        cirq.CNOT(q0, q1)
    )
    return circuit'''
        
        print("Testing Cirq conversion...")
        result = convert_cirq_to_qasm3(test_code)
        print("✓ Conversion successful!")
        print(f"QASM Code:\n{result.qasm_code}")
        assert result is not None
        
    except Exception as e:
        print(f"✗ Cirq conversion failed: {e}")
        return False

def test_pennylane_conversion():
    """Test PennyLane to QASM conversion"""
    try:
        from quantum_converters.converters.pennylane_to_qasm import convert_pennylane_to_qasm3
        
        # Test code with proper format
        test_code = '''import pennylane as qml

def get_circuit():
    dev = qml.device('default.qubit', wires=2)
    
    @qml.qnode(dev)
    def circuit():
        qml.Hadamard(wires=0)
        qml.CNOT(wires=[0, 1])
        return qml.expval(qml.PauliZ(0))
    
    return circuit'''
        
        print("Testing PennyLane conversion...")
        result = convert_pennylane_to_qasm3(test_code)
        print("✓ Conversion successful!")
        print(f"QASM Code:\n{result.qasm_code}")
        assert result is not None
        
    except Exception as e:
        print(f"✗ PennyLane conversion failed: {e}")
        return False

if __name__ == "__main__":
    print("Testing Quantum Framework Conversions...")
    print("=" * 50)
    
    success_count = 0
    total_tests = 3
    
    if test_qiskit_conversion() is None:
        success_count += 1
    print()
    
    if test_cirq_conversion() is None:
        success_count += 1
    print()
    
    if test_pennylane_conversion() is None:
        success_count += 1
    print()
    
    print("=" * 50)
    print(f"Tests completed: {success_count}/{total_tests} successful")
    
    if success_count == total_tests:
        print("✓ All conversions working!")
    else:
        print("✗ Some conversions failed. Check the errors above.")


