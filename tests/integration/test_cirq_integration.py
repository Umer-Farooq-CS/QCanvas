"""
Integration Tests for Cirq to OpenQASM 3.0 Converter

Tests the updated Cirq converter with QASM3Builder integration.

Author: QCanvas Team
Date: 2025-09-30
"""

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from quantum_converters.converters.cirq_to_qasm import CirqToQASM3Converter


class TestCirqIntegration:
    """Test Cirq converter with QASM3Builder integration"""
    
    def test_simple_circuit(self):
        """Test a simple Cirq circuit conversion"""
        source = '''
import cirq

def get_circuit():
    q0, q1 = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(
        cirq.H(q0),
        cirq.CNOT(q0, q1)
    )
    return circuit
'''
        converter = CirqToQASM3Converter()
        result = converter.convert(source)
        
        # Check that conversion was successful
        assert result is not None
        assert result.qasm_code is not None
        
        # Check for expected QASM 3 elements
        qasm = result.qasm_code
        assert "OPENQASM 3.0;" in qasm
        assert 'include "stdgates.inc";' in qasm
        assert "qubit[2] q;" in qasm
        assert "h q[0];" in qasm
        assert "cx q[0], q[1];" in qasm
        
        # Constants are only emitted when required by expressions
        
    def test_parameterized_gates(self):
        """Test Cirq circuit with parameterized gates"""
        source = '''
import cirq
import numpy as np

def get_circuit():
    q = cirq.LineQubit(0)
    circuit = cirq.Circuit(
        cirq.rx(np.pi/2)(q),
        cirq.ry(np.pi/4)(q),
        cirq.rz(np.pi)(q)
    )
    return circuit
'''
        converter = CirqToQASM3Converter()
        result = converter.convert(source)
        
        qasm = result.qasm_code
        assert "rx(pi_2) q[0];" in qasm or "rx(pi/2) q[0];" in qasm
        assert "ry(pi_4) q[0];" in qasm or "ry(pi/4) q[0];" in qasm
        assert "rz(pi) q[0];" in qasm
        
    def test_measurements(self):
        """Test Cirq circuit with measurements"""
        source = '''
import cirq

def get_circuit():
    q0, q1 = cirq.LineQubit.range(2)
    circuit = cirq.Circuit(
        cirq.H(q0),
        cirq.CNOT(q0, q1),
        cirq.measure(q0, key='m0'),
        cirq.measure(q1, key='m1')
    )
    return circuit
'''
        converter = CirqToQASM3Converter()
        result = converter.convert(source)
        
        qasm = result.qasm_code
        assert "bit[2] c;" in qasm
        assert "measure q[0] -> c[0];" in qasm
        assert "measure q[1] -> c[1];" in qasm
        
        # Only the user's operations may appear: the converter used to append a
        # fake `if (c[0] == 1) x q[1];` and an ry loop the user never wrote.
        assert "if (" not in qasm
        assert "for int" not in qasm
        assert "loop_index" not in qasm
        assert "ry(" not in qasm
        assert qasm.count("measure") == 2
        
    def test_inverse_modifier(self):
        """Test inverse gate modifier"""
        source = '''
import cirq

def get_circuit():
    q = cirq.LineQubit(0)
    circuit = cirq.Circuit(
        cirq.S(q)**-1,  # Inverse S gate
        cirq.T(q)**-1   # Inverse T gate
    )
    return circuit
'''
        converter = CirqToQASM3Converter()
        result = converter.convert(source)
        
        qasm = result.qasm_code
        # Should either use inv@ modifier or sdg/tdg gates
        assert "inv @" in qasm or ("sdg" in qasm and "tdg" in qasm)
        
    def test_statistics(self):
        """Test that conversion statistics are calculated"""
        source = '''
import cirq

def get_circuit():
    q0, q1, q2 = cirq.LineQubit.range(3)
    circuit = cirq.Circuit(
        cirq.H(q0),
        cirq.H(q1),
        cirq.H(q2),
        cirq.CNOT(q0, q1),
        cirq.CNOT(q1, q2)
    )
    return circuit
'''
        converter = CirqToQASM3Converter()
        result = converter.convert(source)
        
        # Check statistics
        assert result.stats is not None
        assert result.stats.n_qubits == 3
        assert result.stats.depth is not None
        assert result.stats.gate_counts is not None
        
    def test_reset_instruction(self):
        """Test reset instruction"""
        source = '''
import cirq

def get_circuit():
    q = cirq.LineQubit(0)
    circuit = cirq.Circuit(
        cirq.H(q),
        cirq.reset(q)
    )
    return circuit
'''
        converter = CirqToQASM3Converter()
        result = converter.convert(source)
        
        qasm = result.qasm_code
        assert "reset q[0];" in qasm
        
    def test_multiple_qubit_gates(self):
        """Test two-qubit and three-qubit gates"""
        source = '''
import cirq

def get_circuit():
    q0, q1, q2 = cirq.LineQubit.range(3)
    circuit = cirq.Circuit(
        cirq.CZ(q0, q1),
        cirq.SWAP(q0, q1),
        cirq.TOFFOLI(q0, q1, q2),
        cirq.FREDKIN(q0, q1, q2)
    )
    return circuit
'''
        converter = CirqToQASM3Converter()
        result = converter.convert(source)
        
        qasm = result.qasm_code
        assert "cz q[0], q[1];" in qasm
        assert "swap q[0], q[1];" in qasm
        # Toffoli and Fredkin should be converted
        assert "ccx" in qasm.lower() or "toffoli" in qasm.lower()
        assert "cswap" in qasm.lower() or "fredkin" in qasm.lower()

    def test_controlled_parameterized_gates(self):
        """Test Cirq controlled parameterized gates from Iteration II"""
        source = '''
import cirq
import numpy as np

def get_circuit():
    q0, q1, q2 = cirq.LineQubit.range(3)
    circuit = cirq.Circuit(
        cirq.ControlledGate(cirq.Y)(q0, q1),
        cirq.ControlledGate(cirq.H)(q0, q1),
        cirq.ControlledGate(cirq.rx(np.pi/3))(q0, q1),
        cirq.ControlledGate(cirq.ry(np.pi/4))(q0, q1),
        cirq.ControlledGate(cirq.rz(np.pi/6))(q0, q1),
        cirq.ControlledGate(cirq.ZPowGate(exponent=0.25))(q0, q1),
        cirq.ControlledGate(cirq.ControlledGate(cirq.Z))(q0, q1, q2)
    )
    return circuit
'''
        converter = CirqToQASM3Converter()
        result = converter.convert(source)

        qasm = result.qasm_code
        assert "cy q[0], q[1];" in qasm
        assert "ch q[0], q[1];" in qasm
        assert "crx(" in qasm
        assert "cry(" in qasm
        assert "crz(" in qasm
        assert "cp(" in qasm
        assert "ccz q[0], q[1], q[2];" in qasm


# Run tests if executed directly
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
