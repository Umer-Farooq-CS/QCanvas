"""Unit tests for the new hybrid quantum quality score metrics."""

import pytest
import sys
from pathlib import Path
import cirq
import numpy as np

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.metrics import (
    normalize_circuit_qubits,
    strip_measurements,
    get_baseline_circuit,
    compute_hybrid_quantum_score,
    compute_code_quality_score,
)


class TestHybridQuantumMetrics:
    """Test suite for the hybrid quantum code quality score and helpers."""

    def test_normalize_circuit_qubits(self):
        """Test that qubits are correctly normalized to standard LineQubits."""
        # Create a circuit using GridQubit
        q0 = cirq.GridQubit(0, 0)
        q1 = cirq.GridQubit(1, 1)
        circuit = cirq.Circuit(cirq.H(q0), cirq.CNOT(q0, q1))
        
        normalized = normalize_circuit_qubits(circuit)
        qubits = list(normalized.all_qubits())
        
        # Qubits should be LineQubits and sorted
        assert all(isinstance(q, cirq.LineQubit) for q in qubits)
        assert qubits[0].x == 0
        assert qubits[1].x == 1

    def test_strip_measurements(self):
        """Test that measurement operations are correctly removed."""
        q0, q1 = cirq.LineQubit.range(2)
        circuit = cirq.Circuit(cirq.H(q0), cirq.CNOT(q0, q1), cirq.measure(q0, q1, key="m"))
        
        clean = strip_measurements(circuit)
        
        # Verify no measurement gates exist in the cleaned circuit
        for op in clean.all_operations():
            assert not isinstance(op.gate, cirq.MeasurementGate)
        
        # Verify H and CNOT still exist
        assert len(list(clean.all_operations())) == 2

    def test_get_baseline_circuit(self):
        """Test retrieval and compilation of baseline circuits."""
        # Test BM-001 (Bell State)
        circuit = get_baseline_circuit("BM-001")
        assert circuit is not None
        assert isinstance(circuit, cirq.Circuit)
        
        # Verify it has correct qubits
        qubits = list(circuit.all_qubits())
        assert len(qubits) == 2
        
        # Test non-existent ID
        invalid_circuit = get_baseline_circuit("BM-999")
        assert invalid_circuit is None

    def test_compute_hybrid_quantum_score_exact_match(self):
        """Test that a generated circuit matching baseline gets 1.0 (or high score)."""
        prompt_id = "BM-001"
        gen_circuit = get_baseline_circuit(prompt_id)
        
        score_res = compute_hybrid_quantum_score(
            gen_circuit=gen_circuit,
            prompt_id=prompt_id,
            syntax_valid=True,
            compilation_success=True,
        )
        
        assert score_res["syntax_valid"] is True
        assert score_res["compilation_success"] is True
        assert score_res["fidelity"] == pytest.approx(1.0, abs=1e-5)
        assert score_res["func_gate"] == pytest.approx(1.0, abs=1e-5)
        assert score_res["depth_ratio"] == pytest.approx(1.0, abs=1e-5)
        assert score_res["gate_ratio"] == pytest.approx(1.0, abs=1e-5)
        assert score_res["q_score"] == pytest.approx(1.0, abs=1e-5)

    def test_compute_hybrid_quantum_score_bloated_circuit(self):
        """Test that a bloated circuit with correct state gets penalized."""
        prompt_id = "BM-001"
        q0, q1 = cirq.LineQubit.range(2)
        
        # Double CNOT (which cancels out and produces correct state, but is bloated)
        bloated_circuit = cirq.Circuit(
            cirq.H(q0),
            cirq.CNOT(q0, q1),
            cirq.CNOT(q0, q1),
            cirq.CNOT(q0, q1),
            cirq.measure(q0, q1, key="m")
        )
        
        score_res = compute_hybrid_quantum_score(
            gen_circuit=bloated_circuit,
            prompt_id=prompt_id,
            syntax_valid=True,
            compilation_success=True,
        )
        
        # Fidelity should be 1.0 because the double CNOT cancels out
        assert score_res["fidelity"] == pytest.approx(1.0, abs=1e-5)
        
        # Depth and gate ratios should be less than 1.0 due to bloating
        assert score_res["depth_ratio"] < 1.0
        assert score_res["gate_ratio"] < 1.0
        assert score_res["q_score"] < 1.0

    def test_compute_hybrid_quantum_score_incorrect_state(self):
        """Test that incorrect final state yields a zero score due to gating."""
        prompt_id = "BM-001"
        q0, q1 = cirq.LineQubit.range(2)
        
        # Orthogonal state preparation (prepares |01> instead of Bell state)
        bad_circuit = cirq.Circuit(
            cirq.X(q1),
            cirq.measure(q0, q1, key="result")
        )
        
        score_res = compute_hybrid_quantum_score(
            gen_circuit=bad_circuit,
            prompt_id=prompt_id,
            syntax_valid=True,
            compilation_success=True,
        )
        
        assert score_res["fidelity"] == pytest.approx(0.0, abs=1e-5)
        assert score_res["q_score"] == 0.0  # Fidelity gated

    def test_compute_code_quality_score_with_prompt_id(self):
        """Test that compute_code_quality_score incorporates hybrid scores when prompted."""
        code = """
import cirq
q0, q1 = cirq.LineQubit.range(2)
circuit = cirq.Circuit(cirq.H(q0), cirq.CNOT(q0, q1), cirq.measure(q0, q1, key='result'))
"""
        # We need validation result mock
        import src.evaluation.metrics as metrics
        validation_res = {
            "compilation": {
                "success": True,
                "circuit": cirq.Circuit(
                    cirq.H(cirq.LineQubit(0)),
                    cirq.CNOT(cirq.LineQubit(0), cirq.LineQubit(1)),
                    cirq.measure(cirq.LineQubit(0), cirq.LineQubit(1), key='result')
                )
            }
        }
        
        # Without prompt_id
        res_no_id = compute_code_quality_score(code, validation_result=validation_res)
        assert "code_quality_score" in res_no_id
        assert res_no_id["hybrid_quantum_score"] is None
        
        # With prompt_id
        res_with_id = compute_code_quality_score(code, validation_result=validation_res, prompt_id="BM-001")
        assert res_with_id["hybrid_quantum_score"] is not None
        assert res_with_id["hybrid_quantum_score"] == pytest.approx(1.0, abs=1e-5)
