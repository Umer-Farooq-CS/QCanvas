"""
Optimizer Agent Module

This module implements the Optimizer Agent, responsible for optimizing
quantum circuits for performance, efficiency, and hardware constraints.

Now includes RAG-based optimization guidance that retrieves reference
optimization patterns from the knowledge base.

Author: Umer Farooq, Hussain Waseem Syed, Muhammad Irtaza Khan
Email: umerfarooqcs0891@gmail.com
"""

from __future__ import annotations

from typing import Dict, Any, Optional, List
import os

try:
    import cirq
    CIRQ_AVAILABLE = True
except ImportError:
    CIRQ_AVAILABLE = False

from .base_agent import BaseAgent
from ..tools.analyzer import CircuitAnalyzer
from ..tools.compiler import CirqCompiler
from ..rag.generator import Generator
from ..rag.retriever import Retriever
from ..cirq_rag_code_assistant.config import get_config
from ..cirq_rag_code_assistant.config.logging import get_logger
from ..agent_prompts import OPTIMIZER_SYSTEM

logger = get_logger(__name__)


class OptimizerAgent(BaseAgent):
    """
    Optimizes quantum circuits with RAG-enhanced optimization guidance.
    
    Uses RAG to retrieve reference optimization patterns and apply
    appropriate optimizations based on circuit characteristics.
    """
    
    def __init__(
        self,
        retriever: Optional[Retriever] = None,
        analyzer: Optional[CircuitAnalyzer] = None,
        compiler: Optional[CirqCompiler] = None,
        generator: Optional[Generator] = None,
    ):
        """
        Initialize the OptimizerAgent.
        
        Args:
            retriever: Retriever instance for RAG-based optimization guidance (required)
            analyzer: CircuitAnalyzer instance
            compiler: CirqCompiler instance
            generator: Generator instance for LLM optimization
        """
        super().__init__(name="OptimizerAgent")
        self.retriever = retriever
        if not retriever:
            logger.warning("OptimizerAgent initialized without retriever - RAG guidance disabled")
        
        self.analyzer = analyzer or CircuitAnalyzer()
        self.compiler = compiler or CirqCompiler()
        
        if generator:
            self.generator = generator
        else:
            config = get_config()
            opt_config = config.get("agents", {}).get("optimizer", {}).get("model", {})
            
            self.generator = Generator(
                retriever=retriever,
                model=opt_config.get("model", "anthropic.claude-opus-4-6-v1"),
                provider=opt_config.get("provider", "aws"),
                inference_profile_arn=opt_config.get("inference_profile_arn")
                or os.getenv("BEDROCK_INFERENCE_PROFILE_ARN")
                or os.getenv("BEDROCK_INFERENCE_PROFILE_ARN_OPTIMIZER"),
                temperature=opt_config.get("temperature", 0.2),
                max_tokens=opt_config.get("max_tokens", 2000),
            )
        
        logger.info(f"OptimizerAgent initialized (RAG: {'enabled' if retriever else 'disabled'})")
    
    def _circuit_to_code(self, circuit: "cirq.Circuit") -> str:
        """
        Convert a Cirq Circuit object to executable Python code.

        Uses `repr(circuit)` because Cirq's repr is typically evaluable when `cirq` is imported.
        """
        if not CIRQ_AVAILABLE:
            raise ImportError("Cirq is required to convert circuits to code")

        circuit_repr = repr(circuit)
        return "\n".join(
            [
                "import cirq",
                "",
                f"circuit = {circuit_repr}",
                "",
                "print(circuit)",
            ]
        )
    
    def _retrieve_optimization_references(
        self,
        code: str,
        algorithm: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve optimization references from knowledge base.
        """
        if not self.retriever:
            return []
        
        query_parts = ["optimize", "circuit", "reduce", "depth", "gates"]
        if algorithm:
            query_parts.insert(1, algorithm)
        query = " ".join(query_parts)
        
        try:
            results = self.retriever.retrieve(query=query, top_k=3)
            return results
        except Exception as e:
            logger.warning(f"Failed to retrieve optimization references: {e}")
            return []
    
    def _select_optimizations(
        self,
        circuit: "cirq.Circuit",
        references: List[Dict[str, Any]],
        level: str,
    ) -> List[str]:
        """
        Select which optimizations to apply based on references and circuit analysis.
        
        Returns list of optimization strategy names.
        """
        optimizations = []
        
        optimizations.append("remove_redundant_gates")
        
        if level in ["balanced", "aggressive"]:
            optimizations.append("merge_adjacent_gates")
        
        if level == "aggressive":
            optimizations.append("decompose_multi_qubit")
            optimizations.append("reorder_for_depth")
        
        return optimizations
    
    def execute(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Optimize a quantum circuit with RAG guidance.
        
        Args:
            task: Task dictionary with:
                - code: The Cirq code to optimize
                - circuit: Or a circuit object directly
                - algorithm: Algorithm type for RAG lookup
                - optimization_level: "minimal", "balanced", or "aggressive"
                - use_llm: Whether to use LLM optimization
                - use_heuristics: Whether to use heuristics (default True)
            
        Returns:
            Result dictionary with optimized code and metrics
        """
        code = task.get("code")
        circuit = task.get("circuit")
        algorithm = task.get("algorithm")
        optimization_level = task.get("optimization_level", "balanced")
        
        if not code and not circuit:
            return {
                "success": False,
                "error": "Either 'code' or 'circuit' is required",
            }
        
        try:
            if code:
                compiled = self.compiler.compile(code, execute=True)
                if not compiled["success"] or not compiled.get("circuit"):
                    logger.warning(f"Initial compilation failed: {compiled.get('errors')}")
                    logger.info("Attempting to fix code with LLM...")
                    
                    error_messages = []
                    for err in compiled.get("errors", []):
                        if isinstance(err, dict):
                            error_messages.append(err.get("message", str(err)))
                        else:
                            error_messages.append(str(err))
                    error_desc = "\n".join(error_messages)
                    
                    fix_prompt = f"""Fix the following Google Cirq code that has compilation/execution errors.

Original Code:
{code}

Errors:
{error_desc}

Instructions:
1. Fix all compilation and execution errors
2. Ensure the code creates a circuit variable that can be executed
3. Use the Cirq SDK API: import cirq
4. Ensure the code defines a `circuit` variable (cirq.Circuit) in the global namespace
5. Return ONLY the fixed, executable Cirq code

Fixed code:"""
                    
                    try:
                        fix_result = self.generator.generate_direct(query=fix_prompt, system_prompt=OPTIMIZER_SYSTEM)
                        fixed_code = fix_result.get("code", "")
                        
                        if fixed_code:
                            fixed_compiled = self.compiler.compile(fixed_code, execute=True)
                            if fixed_compiled["success"] and fixed_compiled.get("circuit"):
                                logger.info("LLM successfully fixed compilation errors")
                                code = fixed_code
                                compiled = fixed_compiled
                            else:
                                logger.warning(f"LLM fix still has errors: {fixed_compiled.get('errors')}")
                    except Exception as e:
                        logger.warning(f"LLM fix attempt failed: {e}")
                    
                    if not compiled["success"] or not compiled.get("circuit"):
                        return {
                            "success": False,
                            "error": f"Failed to compile code: {compiled.get('errors')}",
                        }
                
                circuit = compiled["circuit"]
            
            if not CIRQ_AVAILABLE or not isinstance(circuit, cirq.Circuit):
                return {
                    "success": False,
                    "error": "Invalid circuit object",
                }
            
            original_analysis = self.analyzer.analyze(circuit)
            original_code = code if code else self._circuit_to_code(circuit)
            
            references = self._retrieve_optimization_references(code or "", algorithm)
            if references:
                logger.info(f"Retrieved {len(references)} optimization references from RAG")
            
            optimized_circuit = circuit
            optimized_code = original_code
            
            if task.get("use_llm", False):
                logger.info("Running LLM optimization")
                llm_result = self._optimize_with_llm(optimized_code, references)
                if llm_result.get("success"):
                    optimized_code = llm_result["code"]
                    compiled = self.compiler.compile(optimized_code, execute=True)
                    if compiled["success"]:
                        optimized_circuit = compiled["circuit"]
                    else:
                        logger.warning(f"LLM optimization produced invalid code: {compiled.get('errors')}")
                else:
                    logger.warning(f"LLM optimization failed: {llm_result.get('error')}")

            if task.get("use_heuristics", True):
                optimizations = self._select_optimizations(optimized_circuit, references, optimization_level)
                logger.debug(f"Selected optimizations: {optimizations}")
                optimized_code = self._circuit_to_code(optimized_circuit)
            
            optimized_analysis = self.analyzer.analyze(optimized_circuit)
            comparison = self.analyzer.compare(circuit, optimized_circuit)
            
            return {
                "success": True,
                "original_code": original_code,
                "optimized_code": optimized_code,
                "original_metrics": original_analysis["metrics"],
                "optimized_metrics": optimized_analysis["metrics"],
                "improvements": comparison.get("improvements", []),
                "differences": comparison.get("differences", {}),
                "optimizations_applied": self._select_optimizations(circuit, references, optimization_level),
                "rag_references_used": len(references),
            }
        
        except Exception as e:
            logger.error(f"OptimizerAgent error: {e}")
            return {
                "success": False,
                "error": str(e),
            }

    def _optimize_with_llm(
        self,
        code: str,
        references: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Optimize circuit code using LLM with RAG context."""
        context = ""
        if references:
            context_parts = []
            for ref in references[:2]:
                entry = ref.get("entry", {})
                if entry.get("optimized_code"):
                    context_parts.append(f"Example optimization:\n{entry.get('optimized_code')}")
            context = "\n\n".join(context_parts)
        
        prompt = f"""Optimize the following Google Cirq code to reduce circuit depth and gate count while maintaining the same quantum logic.

Original Code:
{code}

{f"Reference optimizations from knowledge base:{chr(10)}{context}" if context else ""}

Instructions:
1. Analyze the circuit for redundant gates and inefficient patterns.
2. Apply circuit identities and optimizations to reduce depth and gate count.
3. CRITICAL: PRESERVE the original qubit initialization method and variable names.
4. Return ONLY the full, executable Cirq code for the optimized circuit.
5. Do not include explanations, just the code.
"""
        
        try:
            result = self.generator.generate_direct(query=prompt, system_prompt=OPTIMIZER_SYSTEM)
            return {
                "success": True,
                "code": result["code"],
                "explanation": result.get("description", "")
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    def _calculate_reward(self, metrics: Dict[str, Any], weights: Dict[str, float]) -> float:
        """Calculate reward based on circuit metrics and weights."""
        reward = 0.0
        
        if "depth" in metrics:
            reward += weights.get("circuit_depth", -0.1) * metrics["depth"]
        if "num_operations" in metrics:
            reward += weights.get("total_gate_count", -0.1) * metrics["num_operations"]
        if "2_qubit_gate_count" in metrics:
            reward += weights.get("two_qubit_gates", -0.5) * metrics["2_qubit_gate_count"]
            
        return reward
