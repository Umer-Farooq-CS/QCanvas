#!/usr/bin/env python3
"""
Simple test script for the API endpoints
"""
import requests
import json

def test_health():
    """Test health endpoint"""
    try:
        response = requests.get("http://127.0.0.1:8000/api/health")
        print(f"Health check: {response.status_code}")
        if response.status_code == 200:
            print(f"Response: {response.json()}")
        assert response.status_code == 200
    except Exception as e:
        print(f"Health check failed: {e}")
        assert False

def test_conversion():
    """Test conversion endpoint"""
    try:
        # Test with proper Qiskit format
        test_code = '''from qiskit import QuantumCircuit

def get_circuit():
    qc = QuantumCircuit(2)
    qc.h(0)
    qc.cx(0, 1)
    return qc'''
        
        payload = {
            "code": test_code,
            "framework": "qiskit",
            "style": "classic"
        }
        
        response = requests.post(
            "http://127.0.0.1:8000/api/converter/convert",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
        
        print(f"Conversion test: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"Success: {result['success']}")
            if result['success']:
                print(f"QASM Code:\n{result['qasm_code']}")
            else:
                print(f"Error: {result['error']}")
        else:
            print(f"Response: {response.text}")
        
        assert response.status_code == 200
    except Exception as e:
        print(f"Conversion test failed: {e}")
        assert False

if __name__ == "__main__":
    print("Testing QCanvas Backend API...")
    print("=" * 40)
    
    health_ok = test_health()
    print()
    
    if health_ok:
        conversion_ok = test_conversion()
        print()
        
        if conversion_ok:
            print("✓ All tests passed!")
        else:
            print("✗ Conversion test failed")
    else:
        print("✗ Health check failed")
        print("Make sure the backend is running on http://127.0.0.1:8000")


