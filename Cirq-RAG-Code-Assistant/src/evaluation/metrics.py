"""
Metrics Collector Module

Collects evaluation metrics including the published code-quality formula
and statistical helpers for multi-trial benchmarks.
"""

import ast
import math
from typing import Dict, Any, List, Optional

from collections import defaultdict

from ..cirq_rag_code_assistant.config.logging import get_logger

logger = get_logger(__name__)

REQUIRED_CIRQ_IMPORTS = ("cirq",)


def _syntax_valid(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def _correct_imports(code: str) -> bool:
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in REQUIRED_CIRQ_IMPORTS:
                    return True
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] in REQUIRED_CIRQ_IMPORTS:
                return True
    return "import cirq" in code or "from cirq" in code


def _has_measurement(code: str, validation_result: Dict[str, Any]) -> bool:
    if "cirq.measure" in code or "cirq.Moment" in code:
        if "measure" in code.lower():
            return True
    compilation = validation_result.get("compilation", {})
    circuit = compilation.get("circuit")
    if circuit is not None:
        try:
            import cirq
            for op in circuit.all_operations():
                if isinstance(op, cirq.GateOperation) and isinstance(
                    op.gate, cirq.MeasurementGate
                ):
                    return True
            if any("measure" in str(m).lower() for m in circuit):
                return True
        except Exception:
            pass
    return "cirq.measure" in code


def _circuit_non_empty(validation_result: Dict[str, Any]) -> bool:
    compilation = validation_result.get("compilation", {})
    circuit = compilation.get("circuit")
    if circuit is not None:
        try:
            return len(list(circuit.all_operations())) > 0
        except Exception:
            pass
    return compilation.get("success", False)


def compute_code_quality_score(
    code: str,
    validation_result: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Published code quality formula (§4.3 revision plan):

    CodeQuality(c) = 0.30 × SyntaxValid
                  + 0.30 × CompilationSuccess
                  + 0.20 × HasMeasurement
                  + 0.10 × CircuitNonEmpty
                  + 0.10 × CorrectImports
    """
    validation_result = validation_result or {}
    compilation = validation_result.get("compilation", {})

    components = {
        "syntax_valid": 1.0 if _syntax_valid(code) else 0.0,
        "compilation_success": 1.0 if compilation.get("success", False) else 0.0,
        "has_measurement": 1.0 if _has_measurement(code, validation_result) else 0.0,
        "circuit_non_empty": 1.0 if _circuit_non_empty(validation_result) else 0.0,
        "correct_imports": 1.0 if _correct_imports(code) else 0.0,
    }

    score = (
        0.30 * components["syntax_valid"]
        + 0.30 * components["compilation_success"]
        + 0.20 * components["has_measurement"]
        + 0.10 * components["circuit_non_empty"]
        + 0.10 * components["correct_imports"]
    )

    return {
        "code_quality_score": score,
        "components": components,
    }


def compute_statistics(values: List[float]) -> Dict[str, float]:
    """Return mean, std, and 95% CI for a list of numeric values."""
    if not values:
        return {"mean": 0.0, "std": 0.0, "ci_lower": 0.0, "ci_upper": 0.0, "n": 0}

    n = len(values)
    mean = sum(values) / n
    if n == 1:
        std = 0.0
    else:
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        std = math.sqrt(variance)

    if n > 1:
        se = std / math.sqrt(n)
        margin = 1.96 * se
    else:
        margin = 0.0

    return {
        "mean": mean,
        "std": std,
        "ci_lower": mean - margin,
        "ci_upper": mean + margin,
        "n": n,
    }


def wilson_ci(successes: int, trials: int, z: float = 1.96) -> Dict[str, float]:
    """Wilson score interval for binomial proportion (success rate)."""
    if trials == 0:
        return {"mean": 0.0, "ci_lower": 0.0, "ci_upper": 0.0, "n": 0}

    p = successes / trials
    denom = 1 + z**2 / trials
    centre = (p + z**2 / (2 * trials)) / denom
    margin = (z / denom) * math.sqrt(p * (1 - p) / trials + z**2 / (4 * trials**2))

    return {
        "mean": p,
        "ci_lower": max(0.0, centre - margin),
        "ci_upper": min(1.0, centre + margin),
        "n": trials,
    }


class MetricsCollector:
    """Collects and aggregates evaluation metrics."""

    def __init__(self):
        """Initialize the MetricsCollector."""
        self.metrics: Dict[str, List[Any]] = defaultdict(list)
        logger.info("Initialized MetricsCollector")

    def collect_code_quality(
        self,
        code: str,
        validation_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Collect code quality metrics using the published formula."""
        quality = compute_code_quality_score(code, validation_result)

        metrics = {
            "code_length": len(code),
            "num_lines": len(code.split("\n")),
            "syntax_valid": quality["components"]["syntax_valid"] == 1.0,
            "compilation_success": quality["components"]["compilation_success"] == 1.0,
            "code_quality_score": quality["code_quality_score"],
            "quality_components": quality["components"],
        }

        self.metrics["code_quality"].append(metrics)
        return metrics

    def collect_agent_performance(
        self,
        agent_name: str,
        stats: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Collect agent performance metrics."""
        metrics = {
            "agent": agent_name,
            "total_requests": stats.get("total_requests", 0),
            "successful_requests": stats.get("successful_requests", 0),
            "failed_requests": stats.get("failed_requests", 0),
            "success_rate": (
                stats.get("successful_requests", 0) / stats.get("total_requests", 1)
                if stats.get("total_requests", 0) > 0
                else 0
            ),
        }

        self.metrics["agent_performance"].append(metrics)
        return metrics

    def get_aggregated_metrics(self) -> Dict[str, Any]:
        """Get aggregated metrics across all collections."""
        aggregated: Dict[str, Any] = {}

        if self.metrics["code_quality"]:
            quality_metrics = self.metrics["code_quality"]
            scores = [m["code_quality_score"] for m in quality_metrics]
            stats = compute_statistics(scores)
            aggregated["code_quality"] = {
                "total_samples": len(quality_metrics),
                "avg_code_length": sum(m["code_length"] for m in quality_metrics)
                / len(quality_metrics),
                "syntax_valid_rate": sum(m["syntax_valid"] for m in quality_metrics)
                / len(quality_metrics),
                "compilation_success_rate": sum(
                    m["compilation_success"] for m in quality_metrics
                )
                / len(quality_metrics),
                "avg_code_quality_score": stats["mean"],
                "code_quality_std": stats["std"],
                "code_quality_ci_lower": stats["ci_lower"],
                "code_quality_ci_upper": stats["ci_upper"],
            }

        if self.metrics["agent_performance"]:
            perf_metrics = self.metrics["agent_performance"]
            aggregated["agent_performance"] = {
                "total_agents": len(perf_metrics),
                "avg_success_rate": sum(m["success_rate"] for m in perf_metrics)
                / len(perf_metrics),
            }

        return aggregated

    def reset(self) -> None:
        """Reset all collected metrics."""
        self.metrics.clear()
