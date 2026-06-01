"""
Benchmark Suite Module

Loads prompts from benchmark_prompts_v2.jsonl (25 prompts) with multi-trial
statistics support. Falls back to STANDARD_BENCHMARKS if the file is missing.
"""

import json
import time
from pathlib import Path
from typing import Dict, Any, List, Optional

from ..orchestration.orchestrator import Orchestrator
from .metrics import (
    MetricsCollector,
    assess_code_objectively,
    compute_code_quality_score,
    compute_statistics,
    wilson_ci,
)
from ..tools.compiler import CirqCompiler
from ..tools.analyzer import CircuitAnalyzer
from ..cirq_rag_code_assistant.config import get_config
from ..cirq_rag_code_assistant.config.logging import get_logger

logger = get_logger(__name__)

DEFAULT_BENCHMARK_PATH = Path("data/datasets/benchmark_prompts_v2.jsonl")

# Legacy fallback (4 prompts) — kept for backward compatibility
STANDARD_BENCHMARKS = [
    {
        "id": "BM-LEGACY-001",
        "tier": "basic",
        "query": "Create a 2-qubit Bell state circuit with measurement",
        "algorithm": "bell_state",
    },
    {
        "id": "BM-LEGACY-002",
        "tier": "intermediate",
        "query": "Implement a 3-qubit Grover search algorithm",
        "algorithm": "grover",
    },
    {
        "id": "BM-LEGACY-003",
        "tier": "algorithm",
        "query": "Create a simple VQE circuit for 2 qubits",
        "algorithm": "vqe",
    },
    {
        "id": "BM-LEGACY-004",
        "tier": "algorithm",
        "query": "Implement a 2-qubit QAOA circuit",
        "algorithm": "qaoa",
    },
]


def load_benchmark_prompts(
    path: Optional[Path] = None,
    tiers: Optional[List[str]] = None,
    exclude_explanation: bool = False,
) -> List[Dict[str, Any]]:
    """
    Load benchmark prompts from JSONL.

    Args:
        path: Path to JSONL file (defaults to config or DEFAULT_BENCHMARK_PATH)
        tiers: Optional filter by tier names
        exclude_explanation: Skip explanation-only prompts (for code-gen benchmarks)
    """
    config = get_config()
    eval_cfg = config.get("evaluation", {})
    configured = eval_cfg.get("benchmark_prompts_path")
    filepath = Path(path) if path else Path(configured or DEFAULT_BENCHMARK_PATH)

    if not filepath.exists():
        logger.warning(f"Benchmark file not found at {filepath}; using STANDARD_BENCHMARKS")
        prompts = list(STANDARD_BENCHMARKS)
    else:
        prompts = []
        with open(filepath, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    prompts.append(json.loads(line))
        logger.info(f"Loaded {len(prompts)} benchmark prompts from {filepath}")

    if exclude_explanation:
        prompts = [p for p in prompts if p.get("tier") != "explanation"]
    if tiers:
        prompts = [p for p in prompts if p.get("tier") in tiers]

    return prompts


def get_validation_from_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Safely extract validation dict (orchestrator initializes keys as None)."""
    for key in ("final_validation", "validation"):
        val = result.get(key)
        if isinstance(val, dict):
            return val
    return {}


def sample_benchmark_cases(
    cases: List[Dict[str, Any]],
    max_cases: int,
) -> List[Dict[str, Any]]:
    """Sample prompts round-robin across tiers so ablations are not all basic-tier."""
    from collections import defaultdict

    by_tier: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for case in cases:
        by_tier[case.get("tier", "unknown")].append(case)

    sampled: List[Dict[str, Any]] = []
    tiers = sorted(by_tier.keys())
    while len(sampled) < max_cases:
        added = False
        for tier in tiers:
            if by_tier[tier] and len(sampled) < max_cases:
                sampled.append(by_tier[tier].pop(0))
                added = True
        if not added:
            break
    return sampled


def _extract_circuit_metrics(code: str, validation: Dict[str, Any]) -> Dict[str, Any]:
    """Extract circuit depth/gate metrics from compiled code when possible."""
    metrics = {
        "circuit_depth": None,
        "num_gates": None,
        "two_qubit_gates": None,
    }
    compilation = validation.get("compilation", {})
    circuit = compilation.get("circuit")
    if circuit is None and code:
        try:
            compiled = CirqCompiler().compile(code, execute=True)
            circuit = compiled.get("circuit")
        except Exception:
            pass

    if circuit is not None:
        try:
            analyzer = CircuitAnalyzer()
            analysis = analyzer.analyze(circuit)
            m = analysis.get("metrics", {})
            metrics["circuit_depth"] = m.get("depth")
            metrics["num_gates"] = m.get("num_operations")
            gates_info = analysis.get("gates", {})
            metrics["two_qubit_gates"] = m.get(
                "two_qubit_gates",
                gates_info.get("num_two_qubit_gates", m.get("num_two_qubit_gates")),
            )
        except Exception as e:
            logger.debug(f"Circuit analysis failed: {e}")

    return metrics


class BenchmarkSuite:
    """Executes benchmarks on the system."""

    def __init__(
        self,
        orchestrator: Orchestrator,
        metrics_collector: Optional[MetricsCollector] = None,
    ):
        self.orchestrator = orchestrator
        self.metrics_collector = metrics_collector or MetricsCollector()
        logger.info("Initialized BenchmarkSuite")

    def run_benchmarks(
        self,
        test_cases: Optional[List[Dict[str, Any]]] = None,
        exclude_explanation: bool = True,
    ) -> Dict[str, Any]:
        """Run each benchmark prompt once."""
        test_cases = test_cases or load_benchmark_prompts(exclude_explanation=exclude_explanation)

        results: Dict[str, Any] = {
            "total_tests": len(test_cases),
            "passed": 0,
            "failed": 0,
            "test_results": [],
            "provider_note": "AWS Bedrock (see config/config.json for per-agent models)",
        }

        logger.info(f"Running {len(test_cases)} benchmark tests...")

        for i, test_case in enumerate(test_cases, 1):
            test_result = self._run_single_case(test_case, test_id=i)
            if test_result["success"] and test_result["validation_passed"]:
                results["passed"] += 1
            else:
                results["failed"] += 1
            results["test_results"].append(test_result)

        results["pass_rate"] = (
            results["passed"] / results["total_tests"] if results["total_tests"] > 0 else 0
        )
        logger.info(f"Benchmark completed: {results['passed']}/{results['total_tests']} passed")
        return results

    def run_benchmarks_multi_trial(
        self,
        test_cases: Optional[List[Dict[str, Any]]] = None,
        num_trials: int = 5,
        exclude_explanation: bool = True,
    ) -> Dict[str, Any]:
        """Run each prompt num_trials times and compute per-prompt statistics."""
        test_cases = test_cases or load_benchmark_prompts(exclude_explanation=exclude_explanation)

        per_prompt: List[Dict[str, Any]] = []
        total_passed = 0
        total_runs = 0

        for i, test_case in enumerate(test_cases, 1):
            trials: List[Dict[str, Any]] = []
            for trial in range(1, num_trials + 1):
                logger.info(
                    f"Prompt {i}/{len(test_cases)} trial {trial}/{num_trials}: "
                    f"{test_case.get('query', '')[:50]}..."
                )
                result = self._run_single_case(test_case, test_id=i, trial=trial)
                trials.append(result)

            successes = sum(1 for t in trials if t["success"] and t["validation_passed"])
            total_passed += successes
            total_runs += num_trials

            latencies = [t["latency_seconds"] for t in trials]
            qualities = [t["code_quality_score"] for t in trials]
            depths = [t["circuit_depth"] for t in trials if t["circuit_depth"] is not None]
            gates = [t["num_gates"] for t in trials if t["num_gates"] is not None]

            prompt_stats = {
                "test_id": test_case.get("id", f"BM-{i:03d}"),
                "tier": test_case.get("tier"),
                "query": test_case.get("query"),
                "algorithm": test_case.get("algorithm"),
                "num_trials": num_trials,
                "success_count": successes,
                "success_rate": successes / num_trials,
                "success_rate_ci": wilson_ci(successes, num_trials),
                "latency_stats": compute_statistics(latencies),
                "code_quality_stats": compute_statistics(qualities),
                "circuit_depth_stats": compute_statistics(depths) if depths else {},
                "gate_count_stats": compute_statistics(gates) if gates else {},
                "trials": trials,
            }
            per_prompt.append(prompt_stats)

        overall_rate = total_passed / total_runs if total_runs > 0 else 0

        return {
            "num_trials_per_prompt": num_trials,
            "total_prompts": len(test_cases),
            "total_runs": total_runs,
            "total_passed": total_passed,
            "overall_pass_rate": overall_rate,
            "overall_pass_rate_ci": wilson_ci(total_passed, total_runs),
            "per_prompt": per_prompt,
            "provider_note": "AWS Bedrock (see config/config.json for per-agent models)",
        }

    def _run_single_case(
        self,
        test_case: Dict[str, Any],
        test_id: int,
        trial: Optional[int] = None,
    ) -> Dict[str, Any]:
        query = test_case.get("query", "")
        algorithm = test_case.get("algorithm")
        tier = test_case.get("tier", "unknown")
        is_explanation = tier == "explanation" or test_case.get("validation_criteria") == "explanation_only"

        start = time.time()
        test_result: Dict[str, Any] = {
            "test_id": test_case.get("id", test_id),
            "tier": tier,
            "query": query,
            "algorithm": algorithm,
            "trial": trial,
            "success": False,
            "validation_passed": False,
            "pipeline_validation_passed": False,
            "errors": [],
            "latency_seconds": 0.0,
            "code_quality_score": 0.0,
            "circuit_depth": None,
            "num_gates": None,
            "two_qubit_gates": None,
        }

        if is_explanation:
            result = self.orchestrator.generate_code(
                query=query,
                algorithm=algorithm,
                optimize=False,
                validate=False,
                final_validate=False,
                explain=True,
            )
            test_result["latency_seconds"] = time.time() - start
            explanation = result.get("explanation") or result.get("explanations", {})
            has_explanation = bool(explanation) and result.get("success", False)
            test_result["success"] = has_explanation
            test_result["validation_passed"] = has_explanation
            test_result["code_quality_score"] = 1.0 if has_explanation else 0.0
            if not has_explanation:
                test_result["errors"] = result.get("errors", ["No explanation generated"])
            return test_result

        result = self.orchestrator.generate_code(
            query=query,
            algorithm=algorithm,
            optimize=True,
            validate=True,
            final_validate=True,
            explain=False,
        )
        test_result["latency_seconds"] = time.time() - start

        validation = get_validation_from_result(result)
        test_result["pipeline_validation_passed"] = validation.get("validation_passed", False)
        test_result["errors"] = result.get("errors", [])

        code = result.get("optimized_code") or result.get("code") or ""
        if code:
            objective_validation = assess_code_objectively(code)
            quality = compute_code_quality_score(code, objective_validation)
            test_result["success"] = objective_validation.get("validation_passed", False)
            test_result["validation_passed"] = objective_validation.get("validation_passed", False)
            test_result["objective_validation"] = objective_validation
            test_result["code_quality_score"] = quality["code_quality_score"]
            test_result["quality_components"] = quality["components"]
            self.metrics_collector.collect_code_quality(code, objective_validation)

            circuit_metrics = _extract_circuit_metrics(code, objective_validation)
            test_result.update(circuit_metrics)

        return test_result
