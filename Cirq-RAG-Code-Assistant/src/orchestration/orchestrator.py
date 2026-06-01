"""
Orchestrator Module

This module implements the main orchestrator that coordinates
all agents and manages the overall workflow.

Pipeline Architecture (from docs):
Designer (Always) → [Validator] → [Optimizer ⟷ Validator Loop] → Final Validator (Always) → [Educational]

Note: Educational Agent runs at the END (after Final Validator) to avoid
resource conflicts when running multiple LLM models simultaneously.

Author: Umer Farooq, Hussain Waseem Syed, Muhammad Irtaza Khan
Email: umerfarooqcs0891@gmail.com
"""

from typing import Dict, Any, Optional
from ..agents.designer import DesignerAgent
from ..agents.optimizer import OptimizerAgent
from ..agents.validator import ValidatorAgent
from ..agents.educational import EducationalAgent
from ..evaluation.metrics import assess_code_objectively, compute_code_quality_score
from ..cirq_rag_code_assistant.config import get_config
from ..cirq_rag_code_assistant.config.logging import get_logger

logger = get_logger(__name__)


class Orchestrator:
    """
    Coordinates multi-agent system for code generation workflow.
    
    Implements the documented pipeline:
    Designer (Always) → [Validator] → [Optimizer ⟷ Validator Loop] → Final Validator (Always) → [Educational]
    
    Note: Educational Agent runs at the END to conserve system resources.
    """
    
    def __init__(
        self,
        designer: DesignerAgent,
        optimizer: Optional[OptimizerAgent] = None,
        validator: Optional[ValidatorAgent] = None,
        educational: Optional[EducationalAgent] = None,
    ):
        """
        Initialize the Orchestrator.
        
        Args:
            designer: DesignerAgent instance (required, always runs first)
            optimizer: Optional OptimizerAgent instance
            validator: Optional ValidatorAgent instance  
            educational: Optional EducationalAgent instance (runs independently)
        """
        self.designer = designer
        self.optimizer = optimizer
        self.validator = validator
        self.educational = educational
        
        # Load configuration
        config = get_config()
        
        # General agent settings
        general_config = config.get("agents", {}).get("general", {})
        self.max_retries = general_config.get("max_retries", 3)
        self.timeout_seconds = general_config.get("timeout_seconds", 300)
        self.parallel_execution = general_config.get("parallel_execution", True)
        
        # Agent enabled flags from config
        self.designer_enabled = config.get("agents", {}).get("designer", {}).get("enabled", True)
        self.optimizer_enabled = config.get("agents", {}).get("optimizer", {}).get("enabled", True)
        self.validator_enabled = config.get("agents", {}).get("validator", {}).get("enabled", True)
        self.educational_enabled = config.get("agents", {}).get("educational", {}).get("enabled", True)
        
        # Optimizer settings
        optimizer_config = config.get("agents", {}).get("optimizer", {})
        self.optimization_level = optimizer_config.get("level", "balanced")
        self.use_rl = optimizer_config.get("use_rl", False)
        self.max_optimization_iterations = optimizer_config.get("rl_iterations", 10)
        
        logger.info(f"Initialized Orchestrator (max_retries={self.max_retries}, timeout={self.timeout_seconds}s)")
        logger.debug(f"Agent states: designer={self.designer_enabled}, optimizer={self.optimizer_enabled}, "
                     f"validator={self.validator_enabled}, educational={self.educational_enabled}")
    
    @staticmethod
    def _normalize_educational_depth(depth: Optional[str]) -> str:
        """Map API/CLI depth strings to EducationalAgent keys."""
        if not depth:
            return "intermediate"
        s = str(depth).lower().replace(" ", "_").replace("-", "_")
        aliases = {"beginner": "low", "advanced": "high", "expert": "very_high"}
        s = aliases.get(s, s)
        allowed = frozenset({"low", "intermediate", "high", "very_high"})
        return s if s in allowed else "intermediate"

    def _score_code(self, code: Optional[str]) -> Dict[str, Any]:
        """Score code with the same objective validation used by the benchmark tables."""
        if not code:
            return {"score": 0.0, "validation": {"validation_passed": False}}

        validation = assess_code_objectively(code)
        quality = compute_code_quality_score(code, validation)
        return {
            "score": quality.get("code_quality_score", 0.0),
            "validation": validation,
            "quality": quality,
        }

    def _prefer_code(self, current_code: str, candidate_code: Optional[str]) -> str:
        """Keep the code version that scores higher under the objective benchmark metric."""
        if not candidate_code:
            return current_code

        current_score = self._score_code(current_code).get("score", 0.0)
        candidate_score = self._score_code(candidate_code).get("score", 0.0)
        return candidate_code if candidate_score >= current_score else current_code

    def generate_code(
        self,
        query: str,
        algorithm: Optional[str] = None,
        designer: bool = True,
        optimize: bool = True,
        validate: bool = True,
        final_validate: bool = True,
        explain: bool = True,
        max_optimization_loops: int = 3,
        educational_depth: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate code with the full pipeline.
        
        Pipeline: Designer → [Validator] → [Optimizer ⟷ Validator Loop] → Final Validator → [Educational]
        
        Note: Educational Agent runs at the END (after Final Validator) to avoid
        resource conflicts from running multiple LLM models simultaneously.
        
        Args:
            query: Natural language query
            algorithm: Optional algorithm type
            optimize: Whether to run optimization stage (conditional)
            validate: Whether to run validation stage (conditional)
            explain: Whether to generate explanations (Educational Agent)
            max_optimization_loops: Max iterations for optimizer ⟷ validator loop
            educational_depth: Explanation depth (low, intermediate, high, very_high)

        Returns:
            Complete result dictionary
        """
        result = {
            "success": False,
            "query": query,
            "algorithm": algorithm,
            "stages": [],  # Track which stages ran
            "code": None,
            "optimized_code": None,
            "validation": None,
            "final_validation": None,
            "explanation": None,
            "errors": [],
        }
        
        try:
            # ===== STAGE 1: Designer (Always Runs) =====
            if designer and self.designer and self.designer_enabled:
                logger.info(f"🎨 [Stage 1/4] Designer Agent generating code...")
                result["stages"].append("designer")
                
                design_result = self._run_with_retry(
                    lambda: self.designer.run({"query": query, "algorithm": algorithm}),
                    stage_name="Designer"
                )
                
                if not design_result.get("success"):
                    result["errors"].append(f"Designer failed: {design_result.get('error')}")
                    return result
                
                result["code"] = design_result.get("code")
                current_code = result["code"]
                logger.info(f"✅ Designer generated code ({len(current_code)} chars)")
            else:
                logger.info(f"⏭️ [Stage 1/4] Designer skipped (disabled or not available)")
                result["errors"].append("Designer is disabled; cannot generate code.")
                return result
            
            # ===== STAGE 2: Validator (Conditional) =====
            if validate and self.validator and self.validator_enabled:
                logger.info(f"✅ [Stage 2/4] Validator Agent checking code...")
                result["stages"].append("validator")
                
                validate_result = self._run_with_retry(
                    lambda: self.validator.execute({
                        "code": current_code,
                        "query": query,
                        "algorithm": algorithm,
                    }),
                    stage_name="Validator"
                )
                
                result["validation"] = validate_result
                repaired_code = validate_result.get("fixed_code") or validate_result.get("llm_analysis", {}).get("fixed_code")
                if repaired_code:
                    improved_code = self._prefer_code(current_code, repaired_code)
                    if improved_code != current_code:
                        logger.info("   Validator repair improved the candidate code; adopting repaired version")
                        current_code = improved_code
                        result["optimized_code"] = current_code
                        result["code"] = current_code
                if not validate_result.get("validation_passed"):
                    logger.warning(f"⚠️ Initial validation found issues")
                    # Continue to optimizer which may fix issues
            else:
                logger.info(f"⏭️ [Stage 2/4] Validator skipped (disabled or not available)")
            
            # ===== STAGE 3: Optimizer with Loop (Conditional) =====
            if optimize and self.optimizer and self.optimizer_enabled:
                logger.info(f"⚡ [Stage 3/4] Optimizer Agent improving code...")
                result["stages"].append("optimizer")
                
                optimization_loop = 0
                while optimization_loop < max_optimization_loops:
                    optimization_loop += 1
                    logger.info(f"   Optimization iteration {optimization_loop}/{max_optimization_loops}")
                    
                    optimize_result = self._run_with_retry(
                        lambda: self.optimizer.execute({
                            "code": current_code,
                            "query": query,
                            "algorithm": algorithm,
                            "optimization_level": self.optimization_level,
                            "use_rl": self.use_rl,
                        }),
                        stage_name="Optimizer"
                    )
                    
                    if optimize_result.get("success"):
                        optimized_code = optimize_result.get("optimized_code")
                        if optimized_code and optimized_code != current_code:
                            chosen_code = self._prefer_code(current_code, optimized_code)
                            current_code = chosen_code
                            result["optimized_code"] = current_code
                            result["code"] = current_code if current_code else result["code"]
                            result["optimization_metrics"] = optimize_result.get("differences", {})
                            
                            # Re-validate after optimization (Optimizer ⟷ Validator loop)
                            if validate and self.validator and optimization_loop < max_optimization_loops:
                                revalidate_result = self.validator.execute({
                                    "code": current_code,
                                    "query": query,
                                    "algorithm": algorithm,
                                })
                                repaired_code = revalidate_result.get("fixed_code") or revalidate_result.get("llm_analysis", {}).get("fixed_code")
                                if repaired_code:
                                    improved_code = self._prefer_code(current_code, repaired_code)
                                    if improved_code != current_code:
                                        logger.info("   Re-validation repair improved the candidate code; adopting repaired version")
                                        current_code = improved_code
                                        result["optimized_code"] = current_code
                                        result["code"] = current_code
                                if revalidate_result.get("validation_passed"):
                                    logger.info(f"   ✅ Re-validation passed, stopping optimization loop")
                                    break
                                else:
                                    logger.info(f"   🔄 Re-validation found issues, continuing optimization...")
                        else:
                            logger.info(f"   No further optimization possible")
                            break
                    else:
                        result["errors"].append(f"Optimization iteration {optimization_loop} failed: {optimize_result.get('error')}")
                        break
                
                logger.info(f"✅ Optimization completed after {optimization_loop} iteration(s)")
            else:
                logger.info(f"⏭️ [Stage 3/4] Optimizer skipped (disabled or not available)")
            
            # ===== STAGE 4: Final Validator (Always Runs) =====
            final_code = result.get("optimized_code") or result["code"]
            
            if final_validate and self.validator and self.validator_enabled:
                logger.info(f"🔍 [Stage 4/4] Final Validator ensuring quality...")
                result["stages"].append("final_validator")
                
                final_validate_result = self._run_with_retry(
                    lambda: self.validator.execute({
                        "code": final_code,
                        "query": query,
                        "algorithm": algorithm,
                    }),
                    stage_name="Final Validator"
                )
                
                result["final_validation"] = final_validate_result
                repaired_code = final_validate_result.get("fixed_code") or final_validate_result.get("llm_analysis", {}).get("fixed_code")
                if repaired_code:
                    improved_code = self._prefer_code(final_code, repaired_code)
                    if improved_code != final_code:
                        logger.info("   Final validation repair improved the candidate code; adopting repaired version")
                        result["optimized_code"] = improved_code
                        result["code"] = improved_code
                        final_code = improved_code
                
                if not final_validate_result.get("validation_passed"):
                    logger.warning(f"⚠️ Final validation has warnings (code may still work)")
                else:
                    logger.info(f"✅ Final validation passed")
            else:
                logger.info(f"⏭️ [Stage 4/4] Final Validator skipped (disabled or not available)")
            
            # ===== STAGE 5: Educational Agent (Runs Last) =====
            # Note: Runs at the END to avoid resource conflicts with other LLM models
            if explain and self.educational and self.educational_enabled:
                depth = self._normalize_educational_depth(educational_depth)
                logger.info(
                    f"📚 [Stage 5/5] Educational Agent generating explanations (depth={depth})..."
                )
                result["stages"].append("educational")
                
                explain_result = self.educational.execute({
                    "code": final_code,
                    "algorithm": algorithm,
                    "depth": depth,
                })
                
                if explain_result.get("success"):
                    result["explanation"] = explain_result.get("explanations", {})
                    result["learning_materials"] = explain_result.get("learning_materials", [])
                    logger.info(f"✅ Educational content generated")
                else:
                    logger.warning(f"⚠️ Educational agent failed: {explain_result.get('error')}")
            
            result["success"] = True
            logger.info(f"🎉 Orchestration completed successfully! Stages run: {result['stages']}")
            
        except Exception as e:
            logger.error(f"Orchestrator error: {e}")
            result["errors"].append(str(e))
        
        return result
    
    def _run_with_retry(self, func, stage_name: str) -> Dict[str, Any]:
        """
        Run a function with retry logic.
        
        Args:
            func: Function to execute
            stage_name: Name of the stage for logging
            
        Returns:
            Function result
        """
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return func()
            except Exception as e:
                last_error = e
                logger.warning(f"{stage_name} attempt {attempt + 1}/{self.max_retries} failed: {e}")
                if attempt < self.max_retries - 1:
                    logger.info(f"Retrying {stage_name}...")
        
        return {"success": False, "error": str(last_error)}
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """
        Get the current pipeline configuration status.
        
        Returns:
            Dictionary with pipeline configuration
        """
        return {
            "designer": {
                "available": self.designer is not None,
                "enabled": self.designer_enabled,
            },
            "validator": {
                "available": self.validator is not None,
                "enabled": self.validator_enabled,
            },
            "optimizer": {
                "available": self.optimizer is not None,
                "enabled": self.optimizer_enabled,
                "level": self.optimization_level,
                "use_rl": self.use_rl,
            },
            "educational": {
                "available": self.educational is not None,
                "enabled": self.educational_enabled,
            },
            "config": {
                "max_retries": self.max_retries,
                "timeout_seconds": self.timeout_seconds,
                "parallel_execution": self.parallel_execution,
            }
        }
