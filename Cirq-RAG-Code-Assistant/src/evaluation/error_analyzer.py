import re
from typing import Dict, Any, List
from collections import defaultdict
from ..cirq_rag_code_assistant.config.logging import get_logger

logger = get_logger(__name__)

ERROR_TAXONOMY = {
    "Syntax Errors": [
        "SyntaxError", "IndentationError", "NameError", "ImportError", "ModuleNotFoundError"
    ],
    "Wrong Cirq API": [
        "AttributeError", "TypeError", "ValueError", "cirq"
    ],
    "Invalid Measurements": [
        "measure", "MeasurementGate", "unmeasured"
    ],
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
        if not errors:
            # If no explicit error string but failed
            if not result.get("validation_passed", False):
                return "Incorrect Quantum Logic"
            return "Unknown Error"

        error_text = " ".join(str(e) for e in errors).lower()

        # Check for syntax errors
        for err_type in ERROR_TAXONOMY["Syntax Errors"]:
            if err_type.lower() in error_text:
                return "Syntax Errors"

        # Check for measurement errors
        if "measure" in error_text or "measurement" in error_text:
            return "Invalid Measurements"

        # Check for wrong Cirq API
        if "cirq" in error_text or "attributeerror" in error_text or "typeerror" in error_text:
            return "Wrong Cirq API"

        # Check for optimizer-induced errors
        if result.get("stage") == "optimization":
            return "Optimizer-Induced Errors"

        # Fallback to incorrect quantum logic if it failed validation but no specific python error
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
