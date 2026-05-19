"""
Ablation Study Module

Runs benchmark prompts across system variants and aggregates metrics
for visualization and paper tables.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from ..orchestration.orchestrator import Orchestrator
from ..agents.designer import DesignerAgent
from ..agents.optimizer import OptimizerAgent
from ..agents.validator import ValidatorAgent
from ..agents.educational import EducationalAgent
from ..rag.retriever import Retriever
from ..rag.generator import Generator
from ..rag.knowledge_base import KnowledgeBase
from .benchmark import (
    load_benchmark_prompts,
    sample_benchmark_cases,
    get_validation_from_result,
    _extract_circuit_metrics,
)
from .metrics import compute_code_quality_score, compute_statistics, wilson_ci
from ..tools.compiler import CirqCompiler
from ..cirq_rag_code_assistant.config.logging import get_logger

logger = get_logger(__name__)

VARIANT_LABELS = {
    "ideal": "Ideal System (Hypothetical)",
    "full": "Full System",
    "no_rag": "No RAG",
    "no_validator": "No Validator",
    "no_optimizer": "No Optimizer",
    "no_final_validator": "No Final Validator",
    "minimal": "Only Designer",
}

VARIANT_COMPONENTS = {
    "ideal": ["Perfect RAG", "Perfect Designer", "Perfect Validator", "Perfect Optimizer"],
    "full": ["RAG", "Designer", "Validator", "Optimizer", "Final Validator"],
    "no_rag": ["Designer", "Validator", "Optimizer", "Final Validator"],
    "no_validator": ["RAG", "Designer", "Optimizer"],
    "no_optimizer": ["RAG", "Designer", "Validator", "Final Validator"],
    "no_final_validator": ["RAG", "Designer", "Validator", "Optimizer"],
    "minimal": ["Designer"],
}

# Variants that run ValidatorAgent during the pipeline
VARIANTS_WITH_VALIDATOR = {"full", "no_rag", "no_optimizer", "no_final_validator"}


def _evaluate_case_outcome(
    variant: str,
    result: Dict[str, Any],
    code: str,
    validation: Dict[str, Any],
    quality: Dict[str, Any],
) -> Tuple[bool, bool]:
    """
    Return (pipeline_success, validation_passed) using the formal code quality score.
    A score of 1.0 means perfect syntax, compilation, measurements, non-empty, and correct imports.
    """
    if not code or not result.get("success", False):
        return False, False

    score = quality.get("code_quality_score", 0.0)
    passed = score >= 0.99
    
    return passed, passed


class AblationStudy:
    """Conducts ablation studies by selectively disabling components."""

    def __init__(self, benchmark_cases: Optional[List[Dict[str, Any]]] = None):
        self.benchmark_cases = benchmark_cases or load_benchmark_prompts(
            exclude_explanation=True
        )
        self.results: Dict[str, Any] = {}

        self.kb = KnowledgeBase()
        self.retriever = Retriever(knowledge_base=self.kb)
        self.generator = Generator(retriever=self.retriever)

        logger.info(f"Initialized AblationStudy with {len(self.benchmark_cases)} cases")

    def run_study(
        self,
        variants: Optional[List[str]] = None,
        max_cases: Optional[int] = None,
        stratified_sample: bool = True,
        num_trials: int = 3,
    ) -> Dict[str, Any]:
        """
        Run ablation study for specified variants.

        Args:
            variants: Variant keys (default: all six notebook modes)
            max_cases: Limit prompts for faster notebook runs
            stratified_sample: If True and max_cases set, sample across tiers
            num_trials: Number of trials per case for statistical variance
        """
        variants = variants or list(VARIANT_LABELS.keys())
        cases = list(self.benchmark_cases)
        if max_cases and max_cases < len(cases):
            if stratified_sample:
                cases = sample_benchmark_cases(cases, max_cases)
            else:
                cases = cases[:max_cases]

        for variant in variants:
            logger.info(f"Running ablation variant: {variant} ({len(cases)} cases, {num_trials} trials)")
            self.results[variant] = self._run_variant(variant, cases, num_trials)

        return self.results

    def aggregate_to_modes_dict(
        self, results: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Dict[str, Any]]:
        """Convert ablation results to the `modes` dict format used by notebook 12."""
        results = results or self.results
        modes: Dict[str, Dict[str, Any]] = {}

        for variant, data in results.items():
            label = VARIANT_LABELS.get(variant, variant)
            lat_stats = data.get("latency_stats", {})
            qual_stats = data.get("code_quality_stats", {})
            depth_stats = data.get("circuit_depth_stats", {})
            gate_stats = data.get("gate_count_stats", {})
            tq_stats = data.get("two_qubit_gate_stats", {})

            modes[label] = {
                "variant_key": variant,
                "components": VARIANT_COMPONENTS.get(variant, []),
                "success_rate": data.get("success_rate", 0.0),
                "success_rate_ci": data.get("success_rate_ci", {}),
                "validation_rate": data.get("validation_rate", 0.0),
                "avg_latency": lat_stats.get("mean", 0.0),
                "latency_std": lat_stats.get("std", 0.0),
                "latency_ci_lower": lat_stats.get("ci_lower", 0.0),
                "latency_ci_upper": lat_stats.get("ci_upper", 0.0),
                "code_length": data.get("avg_code_length", 0),
                "circuit_depth": int(round(depth_stats.get("mean", 0))) if depth_stats else 0,
                "num_gates": int(round(gate_stats.get("mean", 0))) if gate_stats else 0,
                "two_qubit_gates": int(round(tq_stats.get("mean", 0))) if tq_stats else 0,
                "code_quality": qual_stats.get("mean", 0.0),
                "code_quality_std": qual_stats.get("std", 0.0),
                "total_cases": data.get("total_cases", 0),
            }

        return modes

    def save_results(self, path: Path, results: Optional[Dict[str, Any]] = None) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results or self.results, f, indent=2, default=str)
        logger.info(f"Saved ablation results to {path}")
        return path

    @staticmethod
    def load_results(path: Path) -> Dict[str, Any]:
        with open(path, encoding="utf-8") as f:
            return json.load(f)

    def _record_case_metrics(
        self,
        *,
        details: List[Dict[str, Any]],
        case: Dict[str, Any],
        success: bool,
        validation_passed: bool,
        latency: float,
        code: str,
        quality: Dict[str, Any],
        cm: Dict[str, Any],
        result: Dict[str, Any],
        latencies: List[float],
        qualities: List[float],
        code_lengths: List[int],
        depths: List[float],
        gates: List[float],
        two_qubit: List[float],
    ) -> None:
        latencies.append(latency)
        qualities.append(quality["code_quality_score"])
        code_lengths.append(len(code))

        if cm.get("circuit_depth") is not None:
            depths.append(float(cm["circuit_depth"]))
        if cm.get("num_gates") is not None:
            gates.append(float(cm["num_gates"]))
        if cm.get("two_qubit_gates") is not None:
            two_qubit.append(float(cm["two_qubit_gates"]))

        details.append(
            {
                "id": case.get("id"),
                "tier": case.get("tier"),
                "query": case.get("query"),
                "success": success,
                "validation_passed": validation_passed,
                "latency": latency,
                "code_quality_score": quality["code_quality_score"],
                "circuit_depth": cm.get("circuit_depth"),
                "num_gates": cm.get("num_gates"),
                "two_qubit_gates": cm.get("two_qubit_gates"),
                "errors": result.get("errors", []),
            }
        )

    def _mock_ideal_variant(self, variant: str, cases: List[Dict[str, Any]], num_trials: int) -> Dict[str, Any]:
        details = []
        latencies = []
        qualities = []
        depths = []
        gates = []
        two_qubit = []
        code_lengths = []
        
        n = len(cases) * num_trials
        for case in cases:
            for trial in range(num_trials):
                details.append({
                    "id": case.get("id"),
                    "tier": case.get("tier"),
                    "query": case.get("query"),
                    "success": True,
                    "validation_passed": True,
                    "latency": 1.5,
                    "code_quality_score": 1.0,
                    "circuit_depth": 5,
                    "num_gates": 10,
                    "two_qubit_gates": 2,
                    "errors": [],
                })
                latencies.append(1.5)
                qualities.append(1.0)
                code_lengths.append(300)
                depths.append(5.0)
                gates.append(10.0)
                two_qubit.append(2.0)
                
        return {
            "variant": variant,
            "label": VARIANT_LABELS.get(variant, variant),
            "total_cases": len(cases),
            "success_rate": 1.0,
            "success_rate_ci": wilson_ci(n, n),
            "validation_rate": 1.0,
            "avg_latency": 1.5,
            "latency_stats": compute_statistics(latencies),
            "code_quality_stats": compute_statistics(qualities),
            "circuit_depth_stats": compute_statistics(depths),
            "gate_count_stats": compute_statistics(gates),
            "two_qubit_gate_stats": compute_statistics(two_qubit),
            "avg_code_length": 300.0,
            "details": details,
        }

    def _run_variant(self, variant: str, cases: List[Dict[str, Any]], num_trials: int = 1) -> Dict[str, Any]:
        if variant == "ideal":
            return self._mock_ideal_variant(variant, cases, num_trials)

        orchestrator = self._setup_orchestrator(variant)

        details: List[Dict[str, Any]] = []
        success_count = 0
        validation_count = 0
        latencies: List[float] = []
        qualities: List[float] = []
        code_lengths: List[int] = []
        depths: List[float] = []
        gates: List[float] = []
        two_qubit: List[float] = []

        for case in cases:
            for trial in range(num_trials):
                query = case.get("query")
                algorithm = case.get("algorithm")
                case_start = time.time()

                try:
                    result = orchestrator.generate_code(
                        query=query,
                        algorithm=algorithm,
                        optimize=variant not in ("no_optimizer", "minimal"),
                        validate=variant in VARIANTS_WITH_VALIDATOR,
                        final_validate=variant in ("full", "no_rag", "no_optimizer"),
                        explain=False,
                    )
                    latency = time.time() - case_start

                    code = result.get("optimized_code") or result.get("code") or ""
                    validation = get_validation_from_result(result)

                    if not validation and code:
                        compiled = CirqCompiler().compile(code, execute=True)
                        validation = {"compilation": compiled, "validation_passed": compiled.get("success", False)}

                    quality = compute_code_quality_score(code, validation)
                    success, validation_passed = _evaluate_case_outcome(
                        variant, result, code, validation, quality
                    )

                    if success:
                        success_count += 1
                    if validation_passed:
                        validation_count += 1

                    cm = _extract_circuit_metrics(code, validation)
                    self._record_case_metrics(
                        details=details,
                        case=case,
                        success=success,
                        validation_passed=validation_passed,
                        latency=latency,
                        code=code,
                        quality=quality,
                        cm=cm,
                        result=result,
                        latencies=latencies,
                        qualities=qualities,
                        code_lengths=code_lengths,
                        depths=depths,
                        gates=gates,
                        two_qubit=two_qubit,
                    )

                except Exception as e:
                    latency = time.time() - case_start
                    logger.error(f"Error in case {query} ({variant}, trial {trial}): {e}")
                    latencies.append(latency)
                    qualities.append(0.0)
                    code_lengths.append(0)
                    details.append(
                        {
                            "id": case.get("id"),
                            "tier": case.get("tier"),
                            "query": query,
                            "success": False,
                            "validation_passed": False,
                            "latency": latency,
                            "code_quality_score": 0.0,
                            "error": str(e),
                        }
                    )

        n = len(cases) * num_trials or 1
        return {
            "variant": variant,
            "label": VARIANT_LABELS.get(variant, variant),
            "total_cases": len(cases),
            "success_rate": success_count / n,
            "success_rate_ci": wilson_ci(success_count, n),
            "validation_rate": validation_count / n,
            "avg_latency": sum(latencies) / len(latencies) if latencies else 0,
            "latency_stats": compute_statistics(latencies),
            "code_quality_stats": compute_statistics(qualities),
            "circuit_depth_stats": compute_statistics(depths) if depths else {},
            "gate_count_stats": compute_statistics(gates) if gates else {},
            "two_qubit_gate_stats": compute_statistics(two_qubit) if two_qubit else {},
            "avg_code_length": sum(code_lengths) / len(code_lengths) if code_lengths else 0,
            "details": details,
        }

    def _setup_orchestrator(self, variant: str) -> Orchestrator:
        use_rag = variant not in ("no_rag", "minimal")

        if use_rag:
            designer = DesignerAgent(
                retriever=self.retriever, generator=self.generator, use_rag=True
            )
        else:
            no_rag_generator = Generator(retriever=None)
            designer = DesignerAgent(
                retriever=self.retriever,
                generator=no_rag_generator,
                use_rag=False,
            )

        optimizer = (
            OptimizerAgent(retriever=self.retriever)
            if variant not in ("no_optimizer", "minimal")
            else None
        )
        validator = (
            ValidatorAgent(retriever=self.retriever)
            if variant in VARIANTS_WITH_VALIDATOR
            else None
        )
        educational = EducationalAgent(retriever=self.retriever)

        return Orchestrator(
            designer=designer,
            optimizer=optimizer,
            validator=validator,
            educational=educational,
        )
