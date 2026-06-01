"""
Validator Agent Module

This module implements the Validator Agent, responsible for testing,
validating, and ensuring quality of generated Cirq code.

Supports two modes:
- local: Uses local compiler/simulator (original behavior)
- remote: Uses QCanvas backend API for execution + LLM for code fixing

Now includes RAG-based semantic validation that compares circuit outputs
against known-good reference examples with noise tolerance.

Author: Umer Farooq, Hussain Waseem Syed, Muhammad Irtaza Khan
Email: umerfarooqcs0891@gmail.com
"""

import re
import time
import requests
import os
from typing import Dict, Any, Optional, List
from .base_agent import BaseAgent
from ..tools.compiler import CirqCompiler
from ..tools.simulator import QuantumSimulator
from ..tools.analyzer import CircuitAnalyzer
from ..tools.qcanvas_client import QCanvasClient
from ..rag.retriever import Retriever
from ..cirq_rag_code_assistant.config import get_config
from ..cirq_rag_code_assistant.config.logging import get_logger
from ..cirq_rag_code_assistant.bedrock_client import get_bedrock_runtime_client
from ..agent_prompts import VALIDATOR_SYSTEM

logger = get_logger(__name__)


class ValidatorAgent(BaseAgent):
    """
    Validates and tests quantum circuits with RAG-enhanced semantic validation.
    
    Supports local and remote validation modes:
    - local: Uses CirqCompiler, QuantumSimulator, CircuitAnalyzer
    - remote: Uses QCanvas backend API + LLM for intelligent code fixing
    
    RAG Features:
    - Retrieves reference examples for semantic validation
    - Compares measurement distributions against expected outputs
    - Supports noise tolerance for realistic validation
    """
    
    def __init__(
        self,
        mode: Optional[str] = None,
        retriever: Optional[Retriever] = None,
        compiler: Optional[CirqCompiler] = None,
        simulator: Optional[QuantumSimulator] = None,
        analyzer: Optional[CircuitAnalyzer] = None,
        ollama_model: Optional[str] = None,
    ):
        """
        Initialize the ValidatorAgent.
        
        Args:
            mode: Validation mode ("local" or "remote"). Defaults to config value.
            retriever: Retriever instance for RAG-based semantic validation (required)
            compiler: CirqCompiler instance (for local mode)
            simulator: QuantumSimulator instance (for local mode)
            analyzer: CircuitAnalyzer instance (for local mode)
            ollama_model: Ollama model name for LLM fixing (for remote mode)
        """
        super().__init__(name="ValidatorAgent")
        
        self.retriever = retriever
        if not retriever:
            logger.warning("ValidatorAgent initialized without retriever - semantic validation disabled")
        
        config = get_config()
        self.mode = mode or config.get("agents.validator.mode", "local")
        self.llm_enabled = config.get("agents.validator.llm_enabled", True)
        self.default_shots = config.get("agents.validator.default_shots", 1024)
        self.default_backend = config.get("agents.validator.default_backend", "cirq")
        val_model_cfg = config.get("agents", {}).get("validator", {}).get("model", {})
        self.llm_provider = (val_model_cfg.get("provider") or "aws").lower()
        self.llm_model = ollama_model or val_model_cfg.get("model", "anthropic.claude-sonnet-4-6")
        if self.llm_provider == "aws":
            inference_profile_arn = (
                val_model_cfg.get("inference_profile_arn")
                or os.getenv("BEDROCK_INFERENCE_PROFILE_ARN")
                or os.getenv("BEDROCK_INFERENCE_PROFILE_ARN_VALIDATOR")
            )
            if inference_profile_arn:
                logger.info("Using Bedrock inference profile ARN for ValidatorAgent Converse")
                self.llm_model = inference_profile_arn
        self.ollama_model = self.llm_model
        self.ollama_url = config.get("models.ollama_url", "http://localhost:11434")
        if self.llm_provider == "aws":
            try:
                self._bedrock_client = get_bedrock_runtime_client(read_timeout=60)
            except ImportError as e:
                logger.warning(
                    f"AWS Bedrock client unavailable ({e}). Disabling AWS LLM for ValidatorAgent."
                )
                self._bedrock_client = None
                self.llm_enabled = False
        else:
            self._bedrock_client = None
        self.semantic_tolerance_percent = 15

        # Track which execution backend was actually used for validation.
        # Values: "cirq_local", "qcanvas_remote", "cirq_fallback"
        self.execution_backend = "cirq_local"
        
        if self.mode == "local":
            self.compiler = compiler or CirqCompiler()
            self.simulator = simulator or QuantumSimulator()
            self.analyzer = analyzer or CircuitAnalyzer()
        else:
            self.qcanvas_client = QCanvasClient()
            # If QCanvas isn't reachable, fall back to local Cirq tooling automatically.
            if not self.qcanvas_client.check_health():
                logger.warning("QCanvas backend not available; falling back to local Cirq validation")
                self.mode = "local"
                self.execution_backend = "cirq_fallback"
                self.compiler = compiler or CirqCompiler()
                self.simulator = simulator or QuantumSimulator()
                self.analyzer = analyzer or CircuitAnalyzer()
            else:
                self.execution_backend = "qcanvas_remote"
        
        logger.info(f"ValidatorAgent initialized in '{self.mode}' mode (RAG: {'enabled' if retriever else 'disabled'})")
    
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate Cirq code with RAG-enhanced semantic validation and self-correction loop.
        
        Self-Correction: If validation fails, validator uses LLM to fix code and retries
        up to 3 times before giving up.
        
        Args:
            task: Task dictionary with:
                - code: str - The Cirq code to validate
                - algorithm: str (optional) - Algorithm type for RAG lookup
                - query: str (optional) - Original query for context
                - description: str (optional) - What the code should do
                - validation_level: str (optional) - "basic" or "comprehensive"
                - force_llm_fix: bool (optional) - Always use LLM for fixing
                - max_retries: int (optional) - Max validation retries (default 3)
            
        Returns:
            Result dictionary with validation results including semantic validation
        """
        max_validation_retries = task.get("max_retries", 3)
        current_code = task.get("code", "")
        
        for attempt in range(1, max_validation_retries + 1):
            if attempt == 1:
                logger.info(f"Validating code (attempt {attempt}/{max_validation_retries})...")
            else:
                logger.info(f"Re-validating fixed code (attempt {attempt}/{max_validation_retries})...")
            
            attempt_task = task.copy()
            attempt_task["code"] = current_code
            
            if self.mode == "remote":
                result = self._execute_remote(attempt_task)
            else:
                result = self._execute_local(attempt_task)
            
            if self.retriever and result.get("success"):
                semantic_result = self._validate_semantics(
                    code=current_code,
                    algorithm=task.get("algorithm"),
                    simulation_counts=self._extract_counts(result)
                )
                result["semantic_validation"] = semantic_result
                
                if not semantic_result.get("semantic_valid", True):
                    if semantic_result.get("confidence", 0) >= 0.7:
                        result["semantic_warnings"] = semantic_result.get("issues", [])
                        logger.warning(f"Semantic validation warnings: {semantic_result.get('issues')}")
            
            validation_passed = result.get("validation_passed", False)
            
            if validation_passed:
                logger.info(f"Validation passed on attempt {attempt}")
                result["validation_attempts"] = attempt
                return result
            
            if attempt < max_validation_retries:
                if result.get("fixed_code") or result.get("llm_analysis", {}).get("fixed_code"):
                    fixed_code = result.get("fixed_code") or result["llm_analysis"]["fixed_code"]
                    logger.info(f"Using LLM-fixed code for retry...")
                    current_code = self._normalize_code_for_runtime(fixed_code)
                else:
                    logger.warning(f"No LLM fix available, retrying with same code...")
            else:
                logger.warning(f"Validation failed after {max_validation_retries} attempts")
                result["validation_attempts"] = attempt
                return result
        
        return result
    
    def _extract_counts(self, result: Dict[str, Any]) -> Optional[Dict[str, int]]:
        """Extract measurement counts from validation result."""
        if result.get("simulation") and result["simulation"].get("histogram"):
            return result["simulation"]["histogram"]
        if result.get("results") and result["results"].get("counts"):
            return result["results"]["counts"]
        return None

    def _has_measurement_operations(self, circuit: Any) -> bool:
        """Return True if circuit contains at least one measurement operation."""
        try:
            import cirq

            for op in getattr(circuit, "all_operations", lambda: [])():
                gate = getattr(op, "gate", None)
                if gate is not None and isinstance(gate, cirq.MeasurementGate):
                    return True
        except Exception:
            return False
        return False
    
    def _validate_semantics(
        self,
        code: str,
        algorithm: Optional[str],
        simulation_counts: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """
        Validate circuit semantics using RAG references.
        
        Compares simulation output against known-good examples with noise tolerance.
        """
        if not self.retriever:
            return {"semantic_valid": True, "confidence": 0.0, "message": "No retriever available"}
        
        query_parts = ["validate", "circuit", "expected", "output"]
        if algorithm:
            query_parts.insert(1, algorithm)
        query = " ".join(query_parts)
        top_k = get_config().get("rag", {}).get("retrieval", {}).get("top_k_results", 5)
        
        try:
            references = self.retriever.retrieve(query=query, top_k=top_k)
            
            if not references:
                logger.debug("No validation references found")
                return {
                    "semantic_valid": True,
                    "confidence": 0.3,
                    "message": "No reference examples found for comparison"
                }
            
            best_match = None
            best_score = 0
            
            for ref in references:
                entry = ref.get("entry", {})
                ref_algorithm = entry.get("algorithm", "")
                
                if algorithm and ref_algorithm.lower() == algorithm.lower():
                    if ref["score"] > best_score:
                        best_match = entry
                        best_score = ref["score"]
                elif ref["score"] > best_score:
                    best_match = entry
                    best_score = ref["score"]
            
            if not best_match:
                return {
                    "semantic_valid": True,
                    "confidence": 0.3,
                    "message": "No matching reference found"
                }
            
            if simulation_counts and best_match.get("acceptable_ranges"):
                return self._check_output_tolerance(
                    actual_counts=simulation_counts,
                    acceptable_ranges=best_match["acceptable_ranges"],
                    validation_rules=best_match.get("validation_rules", []),
                    reference_id=best_match.get("id", "unknown")
                )
            
            return self._check_code_structure(code, best_match)
            
        except Exception as e:
            logger.error(f"Semantic validation error: {e}")
            return {
                "semantic_valid": True,
                "confidence": 0.0,
                "error": str(e)
            }
    
    def _check_output_tolerance(
        self,
        actual_counts: Dict[str, int],
        acceptable_ranges: Dict[str, Any],
        validation_rules: List[str],
        reference_id: str,
    ) -> Dict[str, Any]:
        """Check if simulation output is within acceptable tolerance ranges."""
        issues = []
        passed_checks = 0
        total_checks = 0
        
        normalized_counts = {}
        for k, v in actual_counts.items():
            key_str = format(int(k), 'b') if isinstance(k, int) else str(k)
            normalized_counts[key_str] = v
        
        for state, range_spec in acceptable_ranges.items():
            if state == "all_states":
                for count_state, count_val in normalized_counts.items():
                    total_checks += 1
                    min_val = range_spec.get("min", 0)
                    max_val = range_spec.get("max", float('inf'))
                    if min_val <= count_val <= max_val:
                        passed_checks += 1
                    else:
                        issues.append(f"State {count_state}: {count_val} not in [{min_val}, {max_val}]")
            elif isinstance(range_spec, dict):
                total_checks += 1
                actual_val = normalized_counts.get(state, 0)
                min_val = range_spec.get("min", 0)
                max_val = range_spec.get("max", float('inf'))
                
                if min_val <= actual_val <= max_val:
                    passed_checks += 1
                else:
                    issues.append(f"State '{state}': got {actual_val}, expected [{min_val}, {max_val}]")
        
        pass_rate = passed_checks / max(total_checks, 1)
        semantic_valid = pass_rate >= 0.7
        
        return {
            "semantic_valid": semantic_valid,
            "confidence": pass_rate,
            "reference_id": reference_id,
            "checks_passed": passed_checks,
            "checks_total": total_checks,
            "issues": issues,
            "validation_rules": validation_rules,
            "actual_counts": normalized_counts,
        }
    
    def _check_code_structure(
        self,
        code: str,
        reference: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Compare code structure against reference when simulation isn't available."""
        issues = []
        code_lower = code.lower()
        
        common_errors = reference.get("common_errors", [])
        for error in common_errors:
            if "missing hadamard" in error.lower() and ".h(" not in code_lower:
                issues.append("Possible missing Hadamard gate")
            if "missing x gate" in error.lower() and ".x(" not in code_lower:
                issues.append("Possible missing X gate")
        
        algorithm = reference.get("algorithm", "")
        if algorithm == "bell_state":
            if ".h(" not in code_lower:
                issues.append("Bell state should have Hadamard gate")
            if ".cnot(" not in code_lower and ".cx(" not in code_lower:
                issues.append("Bell state should have CNOT gate")
        elif algorithm == "grover":
            if ".cz(" not in code_lower and ".ccnot(" not in code_lower:
                issues.append("Grover's algorithm should have controlled-Z for oracle/diffuser")
        
        semantic_valid = len(issues) == 0
        confidence = 1.0 if semantic_valid else max(0.3, 1.0 - len(issues) * 0.2)
        
        return {
            "semantic_valid": semantic_valid,
            "confidence": confidence,
            "reference_id": reference.get("id", "unknown"),
            "issues": issues,
            "check_type": "structure",
        }
    
    def _execute_remote(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute validation via QCanvas backend API."""
        code = task.get("code", "")
        description = task.get("description", "")
        shots = task.get("shots", self.default_shots)
        
        if not code:
            return {
                "success": False,
                "error": "Code is required",
            }
        
        try:
            exec_result = self.qcanvas_client.validate_and_execute(
                code=code,
                shots=shots,
                backend=self.default_backend
            )
            
            if self.llm_enabled and (not exec_result["success"] or task.get("force_llm_fix")):
                llm_result = self.fix_code_with_llm(code, description, exec_result)
                exec_result["llm_analysis"] = llm_result
                exec_result["fixed_code"] = llm_result.get("fixed_code")
            
            exec_result["validation_passed"] = exec_result.get("success", False)
            exec_result["details"] = {
                "execution_backend": "qcanvas_remote",
                "qcanvas_url": getattr(self.qcanvas_client, "base_url", None),
            }
            
            return exec_result
            
        except Exception as e:
            logger.error(f"ValidatorAgent remote execution error: {e}")
            # Automatic fallback to local Cirq validation if QCanvas is unavailable.
            fallback = self._execute_local(task)
            fallback.setdefault("details", {})
            if isinstance(fallback["details"], dict):
                fallback["details"].update(
                    {
                        "execution_backend": "cirq_fallback",
                        "qcanvas_error": str(e),
                        "qcanvas_url": getattr(getattr(self, "qcanvas_client", None), "base_url", None),
                    }
                )
            return fallback
    
    def _execute_local(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute validation using local compiler/simulator."""
        code = task.get("code", "")
        validation_level = task.get("validation_level", "comprehensive")
        require_measurements = task.get("require_measurements", validation_level == "comprehensive")
        
        if not code:
            return {
                "success": False,
                "error": "Code is required",
            }
        
        try:
            compilation = self.compiler.compile(code, execute=True)
            
            if not compilation["success"]:
                first_err = (
                    compilation.get("errors", ["Compilation failed"])[0]
                    if compilation.get("errors")
                    else "Compilation failed"
                )
                err_str = (
                    first_err.get("message", str(first_err))
                    if isinstance(first_err, dict)
                    else first_err
                )
                result = {
                    "success": False,
                    "validation_passed": False,
                    "stage": "compilation",
                    "errors": compilation["errors"],
                    "compilation": compilation,
                    "error": err_str,
                    "details": {"execution_backend": "cirq_local"},
                }
                
                if self.llm_enabled:
                    description = task.get("description", "")
                    exec_result = {
                        "success": False,
                        "stage": "compilation",
                        "error": result.get("error"),
                    }
                    logger.info("Running LLM analysis for compilation error fixing...")
                    llm_result = self.fix_code_with_llm(code, description, exec_result)
                    result["llm_analysis"] = llm_result
                    result["fixed_code"] = llm_result.get("fixed_code")
                
                return result
            
            circuit = compilation.get("circuit")
            if not circuit:
                result = {
                    "success": False,
                    "validation_passed": False,
                    "stage": "compilation",
                    "error": "No circuit found in code",
                    "details": {"execution_backend": "cirq_local"},
                }
                
                if self.llm_enabled:
                    description = task.get("description", "")
                    exec_result = {
                        "success": False,
                        "stage": "compilation",
                        "error": result.get("error"),
                    }
                    logger.info("Running LLM analysis for circuit detection error...")
                    llm_result = self.fix_code_with_llm(code, description, exec_result)
                    result["llm_analysis"] = llm_result
                    result["fixed_code"] = llm_result.get("fixed_code")
                
                return result
            
            circuit_validation = self.compiler.validate_circuit(circuit)
            analysis = self.analyzer.analyze(circuit)
            has_measurements = self._has_measurement_operations(circuit)

            if require_measurements and not has_measurements:
                result = {
                    "success": False,
                    "validation_passed": False,
                    "stage": "circuit_validation",
                    "compilation": compilation,
                    "circuit_validation": circuit_validation,
                    "analysis": analysis,
                    "simulation": None,
                    "results": {
                        "counts": {},
                        "probs": None,
                    },
                    "errors": compilation.get("errors", []) + circuit_validation.get("errors", []),
                    "error": "Circuit has no measurement operations",
                    "details": {"execution_backend": "cirq_local"},
                }
                result["errors"].append("Circuit has no measurement operations")

                if self.llm_enabled:
                    description = task.get("description", "")
                    exec_result = {
                        "success": False,
                        "stage": result["stage"],
                        "error": result.get("error"),
                        "results": result.get("results"),
                    }
                    logger.info("Running LLM analysis for missing measurement fixing...")
                    llm_result = self.fix_code_with_llm(code, description, exec_result)
                    result["llm_analysis"] = llm_result
                    result["fixed_code"] = llm_result.get("fixed_code")

                return result
            
            simulation_result = None
            simulation_success = True
            
            if validation_level == "comprehensive":
                simulation_result = self.simulator.simulate(circuit, repetitions=self.default_shots)
                simulation_success = simulation_result.get("success", False)
                
                if not simulation_success:
                    sim_error = simulation_result.get("error", "Unknown simulation error")
                    logger.warning(f"Simulation failed: {sim_error}")
            
            validation_passed = (
                compilation["success"] and
                circuit_validation["valid"] and
                simulation_success
            )
            
            result = {
                "success": True,
                "validation_passed": validation_passed,
                "stage": "simulation" if simulation_success else "simulation_failed",
                "compilation": compilation,
                "circuit_validation": circuit_validation,
                "analysis": analysis,
                "simulation": simulation_result,
                "errors": compilation.get("errors", []) + circuit_validation.get("errors", []),
                "details": {"execution_backend": "cirq_local"},
            }
            
            if simulation_result and not simulation_success:
                sim_error = simulation_result.get("error", "Simulation failed")
                result["errors"].append(sim_error)
                result["error"] = sim_error
            
            if simulation_result and simulation_result.get("histogram"):
                result["results"] = {
                    "counts": simulation_result["histogram"],
                    "probs": None,
                    "metadata": {
                        "execution_time": f"{simulation_result.get('execution_time', 0) * 1000:.2f}ms",
                        "backend": "cirq_local",
                        "shots": self.default_shots,
                    }
                }
            else:
                result["results"] = {
                    "counts": {},
                    "probs": None,
                }
            
            if self.llm_enabled and (not validation_passed or task.get("force_llm_fix")):
                description = task.get("description", "")
                
                exec_result = {
                    "success": validation_passed,
                    "stage": result["stage"],
                    "error": result.get("error"),
                    "results": result.get("results"),
                }
                
                logger.info("Running LLM analysis for code fixing...")
                llm_result = self.fix_code_with_llm(code, description, exec_result)
                result["llm_analysis"] = llm_result
                result["fixed_code"] = llm_result.get("fixed_code")
            
            return result
            
        except Exception as e:
            logger.error(f"ValidatorAgent local execution error: {e}")
            return {
                "success": False,
                "validation_passed": False,
                "stage": "error",
                "error": str(e),
                "details": {"execution_backend": "cirq_local"},
            }
    
    def fix_code_with_llm(
        self, 
        code: str, 
        description: str, 
        exec_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Use LLM to analyze execution results and fix the code.
        
        Args:
            code: Original Cirq code
            description: What the code should do
            exec_result: Execution result
            
        Returns:
            Dictionary with fixed_code, analysis, success
        """
        prompt = self._format_llm_prompt(code, description, exec_result)
        
        try:
            response = self._call_llm(prompt)
            return self._parse_llm_response(response)
        except Exception as e:
            logger.error(f"LLM fix_code error: {e}")
            return {
                "success": False,
                "error": str(e),
                "fixed_code": None,
                "analysis": None
            }
    
    def _format_llm_prompt(
        self, 
        code: str, 
        description: str, 
        exec_result: Dict[str, Any]
    ) -> str:
        """Format prompt for the Validator LLM."""
        raw_error = exec_result.get("error", "")
        error_str = (
            raw_error.get("message", str(raw_error))
            if isinstance(raw_error, dict)
            else (raw_error if isinstance(raw_error, str) else str(raw_error))
        )
        error_info = ""
        if error_str:
            error_info = f"\n\n**ERROR:**\n{error_str}"

        results_info = ""
        if exec_result.get("results"):
            results = exec_result["results"]
            counts = results.get("counts", {})
            probs = results.get("probs", {})
            results_info = f"\n\n**SIMULATION RESULTS:**\nCounts: {counts}\nProbabilities: {probs}"
        
        stage = exec_result.get("stage", "unknown")
        circuit_detection_guidance = ""

        if "circuit" in error_str.lower() and ("not found" in error_str.lower() or "detection" in error_str.lower()):
            circuit_detection_guidance = """

**CRITICAL FIXING INSTRUCTIONS FOR CIRCUIT DETECTION ERROR:**
1. The code must create a circuit variable in the global namespace (e.g., `circuit = cirq.Circuit(...)`)
2. If the code defines a function that returns a circuit, you MUST call that function and assign the result to a variable named `circuit`
3. For VQE patterns: If you have a function like `vqe_ansatz(theta)`, call it and assign: `circuit = vqe_ansatz([0.0, 0.0])` or similar
4. The circuit variable must be accessible after code execution, not just inside a function
5. Always ensure the final circuit is assigned to a variable named `circuit` for compatibility

Example fix pattern:
```python
import cirq

def create_circuit():
    q0, q1 = cirq.LineQubit.range(2)
    return cirq.Circuit(
        cirq.H(q0),
        cirq.CNOT(q0, q1),
        cirq.measure(q0, q1, key="m"),
    )

circuit = create_circuit()
```
"""
        
        qaoa_guidance = ""
        if "qaoa" in (description or "").lower() or "qaoa" in (code or "").lower():
            qaoa_guidance = """

**QAOA-SPECIFIC CONSTRAINTS (CIRQ):**
- Use `cirq.ZZPowGate(exponent=...)` for problem Hamiltonian terms on edges.
- Use `cirq.rx(...)` for the mixer on each qubit.
- Ensure measurement exists (e.g., `cirq.measure(*qubits, key="m")`).
"""

        cirq_api_guidance = """

**CIRQ API NOTES (IMPORTANT):**
- Use `cirq.Simulator().run(circuit, repetitions=...)` for sampling-based validation.
- Use stable measurement keys and consistent qubit ordering.
"""
        
        prompt = f"""**ORIGINAL CIRQ CODE:**
```python
{code}
```

**DESCRIPTION OF EXPECTED BEHAVIOR:**
{description or "Not specified"}

**EXECUTION STAGE:** {stage}
**SUCCESS:** {exec_result.get("success", False)}{error_info}{results_info}{circuit_detection_guidance}{qaoa_guidance}{cirq_api_guidance}

Please analyze this code and its execution results. If there are issues, provide a fixed version of the code that:
1. Fixes all compilation and execution errors
2. Creates a circuit variable in the global namespace
3. Is fully executable and can be validated
4. Follows Google Cirq best practices

Return the fixed code in a markdown code block."""
        
        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """Call the configured LLM (Ollama or AWS Bedrock) with the validator model."""
        if self.llm_provider == "aws":
            return self._call_bedrock(prompt)
        return self._call_ollama(prompt)

    def _call_bedrock(self, prompt: str, max_retries: int = 5) -> str:
        """Call AWS Bedrock Converse API with the validator model. Retries on throttle with backoff."""
        last_error = None
        for attempt in range(max_retries):
            try:
                response = self._bedrock_client.converse(
                    modelId=self.llm_model,
                    messages=[{"role": "user", "content": [{"text": prompt}]}],
                    system=[{"text": VALIDATOR_SYSTEM}],
                    inferenceConfig={"maxTokens": 2048, "temperature": 0.2},
                )
                return response["output"]["message"]["content"][0]["text"]
            except Exception as e:
                last_error = e
                err_msg = str(e).lower()
                if (
                    self.llm_provider == "aws"
                    and ("on-demand throughput" in err_msg or "inference profile" in err_msg)
                ):
                    raise RuntimeError(
                        "Bedrock Converse requires an Inference Profile for this model/throughput. "
                        "Create an inference profile for the configured Anthropic model and set "
                        "`agents.validator.model.inference_profile_arn` (or env var "
                        "`BEDROCK_INFERENCE_PROFILE_ARN_VALIDATOR`) in config.json."
                    ) from e
                err_code = None
                if hasattr(e, "response") and isinstance(getattr(e, "response", None), dict):
                    err_code = e.response.get("Error", {}).get("Code")
                is_throttle = err_code == "ThrottlingException" or "Throttling" in type(e).__name__
                if is_throttle and attempt < max_retries - 1:
                    wait = 15 * (attempt + 1)
                    logger.warning(
                        "Bedrock throttled, waiting %ds before retry (%d/%d)",
                        wait, attempt + 1, max_retries,
                    )
                    time.sleep(wait)
                else:
                    raise
        raise last_error

    def _call_ollama(self, prompt: str) -> str:
        """Call Ollama API with the validator model."""
        try:
            response = requests.post(
                f"{self.ollama_url}/api/generate",
                json={
                    "model": self.ollama_model,
                    "prompt": prompt,
                    "stream": False
                },
                timeout=60
            )
            
            if response.status_code == 200:
                resp_text = response.json().get("response", "")
                logger.debug(f"LLM Prompt: {prompt}")
                logger.debug(f"LLM Response: {resp_text}")
                return resp_text
            else:
                raise Exception(f"Ollama API error: {response.status_code}")
                
        except requests.exceptions.ConnectionError:
            raise Exception(f"Cannot connect to Ollama at {self.ollama_url}")
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse the LLM response to extract fixed code and analysis."""
        result = {
            "success": True,
            "fixed_code": None,
            "analysis": None,
            "raw_response": response
        }
        
        code_pattern = r'```(?:python)?\s*\n(.*?)\n```'
        code_match = re.search(code_pattern, response, re.DOTALL)
        
        if code_match:
            result["fixed_code"] = self._normalize_code_for_runtime(code_match.group(1).strip())
            
            code_end = code_match.end()
            analysis = response[code_end:].strip()
            if analysis:
                result["analysis"] = analysis
        else:
            result["analysis"] = response.strip()
            result["success"] = False
        
        return result

    def _normalize_code_for_runtime(self, code: str) -> str:
        """
        Normalize common Cirq API mismatches in generated code.

        The validator runs code via `exec()`. If the LLM generates code against a different
        Cirq version, runtime errors can prevent validation.
        """
        if not code:
            return code
        return code
    
    def check_backend_health(self) -> bool:
        """Check if QCanvas backend is available (remote mode only)."""
        if self.mode == "remote":
            return self.qcanvas_client.check_health()
        return True
