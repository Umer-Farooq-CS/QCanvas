#!/usr/bin/env python3
"""
Test PennyLane conversion
"""
from app.services.conversion_service import ConversionService

def test_pennylane():
    cs = ConversionService()
    
    # Test PennyLane code
    pennylane_code = '''import pennylane as qml

def get_circuit():
    dev = qml.device("default.qubit", wires=2)
    
    @qml.qnode(dev)
    def circuit():
        qml.Hadamard(wires=0)
        qml.CNOT(wires=[0, 1])
        return qml.expval(qml.PauliZ(0))
    
    return circuit'''
    
    result = cs.convert_to_qasm(pennylane_code, 'pennylane')
    print("PennyLane Conversion Result:")
    print(f"Success: {result['success']}")
    if result['success']:
        print(f"QASM Code:\n{result['qasm_code']}")
        print(f"Stats: {result['conversion_stats']}")
    else:
        print(f"Error: {result['error']}")

if __name__ == "__main__":
    test_pennylane()
