"""Unit tests for the ErrorAnalyzer failure classification module."""

import pytest
import sys
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.error_analyzer import ErrorAnalyzer


class TestErrorAnalyzer:
    """Test suite for ErrorAnalyzer failure classification."""

    def test_syntax_errors(self):
        """Test classification of Python syntax and parser errors."""
        analyzer = ErrorAnalyzer()
        res = {
            "success": False,
            "errors": ["SyntaxError: invalid syntax", "IndentationError: unexpected indent"]
        }
        assert analyzer.categorize_failure(res) == "Syntax Errors"

    def test_wrong_cirq_api(self):
        """Test classification of deprecated methods, legacy APIs, and attribute errors."""
        analyzer = ErrorAnalyzer()
        res = {
            "success": False,
            "errors": ["AttributeError: module 'cirq' has no attribute 'contrib'", "TypeError: unexpected keyword argument 'exponent'"]
        }
        assert analyzer.categorize_failure(res) == "Wrong Cirq API"

    def test_invalid_measurements(self):
        """Test classification of missing or misconfigured measurement gates."""
        analyzer = ErrorAnalyzer()
        res = {
            "success": False,
            "errors": ["ValueError: Circuit has no measurement operations", "unmeasured qubits in simulator run"]
        }
        assert analyzer.categorize_failure(res) == "Invalid Measurements"

    def test_poor_rag_retrieval(self):
        """Test classification when RAG fails to retrieve relevant templates."""
        analyzer = ErrorAnalyzer()
        res = {
            "success": False,
            "rag_references_used": 0,
            "errors": []
        }
        assert analyzer.categorize_failure(res) == "Poor RAG Retrieval"

    def test_optimizer_induced_errors(self):
        """Test classification of errors triggered during the optimization stage."""
        analyzer = ErrorAnalyzer()
        res = {
            "success": False,
            "stage": "optimization",
            "errors": ["ValueError: empty circuit after optimization"]
        }
        assert analyzer.categorize_failure(res) == "Optimizer-Induced Errors"

    def test_explanation_inaccuracies(self):
        """Test classification of errors stemming from the Educational agent's descriptions."""
        analyzer = ErrorAnalyzer()
        res = {
            "success": False,
            "errors": ["bra-ket mismatch in the generated explanation", "invalid description from educational agent"]
        }
        assert analyzer.categorize_failure(res) == "Explanation Inaccuracies"

    def test_incorrect_quantum_logic(self):
        """Test classification of logical errors or state vector simulation failures."""
        analyzer = ErrorAnalyzer()
        res = {
            "success": False,
            "validation_passed": False,
            "errors": []
        }
        assert analyzer.categorize_failure(res) == "Incorrect Quantum Logic"
        
        res_with_err = {
            "success": False,
            "errors": ["quantum state validation failed", "fidelity mismatch against baseline"]
        }
        assert analyzer.categorize_failure(res_with_err) == "Incorrect Quantum Logic"

    def test_analyze_results(self):
        """Test aggregation and counting of failures in multiple runs."""
        analyzer = ErrorAnalyzer()
        results = [
            {"success": False, "errors": ["SyntaxError: invalid syntax"]},
            {"success": False, "errors": ["SyntaxError: invalid syntax"]},
            {"success": False, "errors": ["ValueError: Circuit has no measurement operations"]},
            {"success": True, "validation_passed": True, "errors": []}, # Should be ignored (success)
            {"success": False, "errors": ["AttributeError: no attribute 'contrib'"]}
        ]
        counts = analyzer.analyze_results(results)
        assert counts == {
            "Syntax Errors": 2,
            "Invalid Measurements": 1,
            "Wrong Cirq API": 1
        }
