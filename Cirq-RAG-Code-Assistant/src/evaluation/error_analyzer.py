import re
from typing import Dict, Any, List
from collections import defaultdict
from ..cirq_rag_code_assistant.config.logging import get_logger

logger = get_logger(__name__)

ERROR_TAXONOMY = {
    "Syntax Errors": [
        "syntaxerror", "indentationerror", "nameerror", "importerror", "modulenotfounderror"
    ],
    "Wrong Cirq API": [
        "attributeerror", "typeerror", "valueerror", "cirq.contrib", "deprecated", "no attribute", "unexpected keyword argument"
    ],
    "Invalid Measurements": [
        "measurement", "measure", "unmeasured", "no measurement operations", "missing measurement"
    ],
    "Poor RAG Retrieval": [
        "retrieval", "no context", "empty knowledge base", "similarity threshold"
    ],
    "Optimizer-Induced Errors": [
        "optimization failed", "empty circuit", "optimizer-induced", "depth reduction error"
    ],
    "Explanation Inaccuracies": [
        "explanation", "educational agent", "invalid description", "bra-ket mismatch"
    ],
    "Incorrect Quantum Logic": [
        "incorrect state", "fidelity mismatch", "logic error", "quantum state validation failed"
    ]
}

class ErrorAnalyzer:
    """Analyzes and categorizes failure modes according to the error taxonomy."""

    def __init__(self):
        logger.info("Initialized ErrorAnalyzer")
        self.error_counts = defaultdict(int)

    def categorize_failure(self, result: Dict[str, Any]) -> str:
        """
        Inspects the result dictionary and maps the failure to a category in the taxonomy.
        """
        errors = result.get("errors", [])
        stage = result.get("stage", "")
        
        # Prioritize optimizer-induced errors if the stage matches
        if stage in ("optimization", "optimizer", "optimizing"):
            return "Optimizer-Induced Errors"
            
        if not errors:
            # If no explicit error string but validation/success failed
            if not result.get("validation_passed", False) or not result.get("success", False):
                if result.get("rag_references_used") == 0:
                    return "Poor RAG Retrieval"
                return "Incorrect Quantum Logic"
            return "Unknown Error"

        error_text = " ".join(str(e) for e in errors).lower()

        # Check for syntax errors
        for keyword in ERROR_TAXONOMY["Syntax Errors"]:
            if keyword in error_text:
                return "Syntax Errors"

        # Check for explanation errors
        for keyword in ERROR_TAXONOMY["Explanation Inaccuracies"]:
            if keyword in error_text:
                return "Explanation Inaccuracies"

        # Check for measurement errors
        for keyword in ERROR_TAXONOMY["Invalid Measurements"]:
            if keyword in error_text:
                return "Invalid Measurements"

        # Check for optimizer-induced errors
        for keyword in ERROR_TAXONOMY["Optimizer-Induced Errors"]:
            if keyword in error_text:
                return "Optimizer-Induced Errors"

        # Check for poor RAG retrieval
        for keyword in ERROR_TAXONOMY["Poor RAG Retrieval"]:
            if keyword in error_text:
                return "Poor RAG Retrieval"

        # Check for wrong Cirq API
        for keyword in ERROR_TAXONOMY["Wrong Cirq API"]:
            if keyword in error_text:
                return "Wrong Cirq API"

        # Check for incorrect quantum logic
        for keyword in ERROR_TAXONOMY["Incorrect Quantum Logic"]:
            if keyword in error_text:
                return "Incorrect Quantum Logic"

        # Fallbacks
        if "cirq" in error_text or "attributeerror" in error_text or "typeerror" in error_text:
            return "Wrong Cirq API"

        return "Incorrect Quantum Logic"

    def analyze_results(self, test_results: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Analyzes a list of test results and returns the frequency of each error category.
        """
        for result in test_results:
            if not result.get("success", False) or not result.get("validation_passed", False):
                category = self.categorize_failure(result)
                self.error_counts[category] += 1
                
        return dict(self.error_counts)
