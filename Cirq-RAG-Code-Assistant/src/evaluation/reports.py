"""
Report Generator Module

Generates evaluation reports with mean ± std and 95% CI columns.
"""

import json
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime
from .metrics import MetricsCollector
from .benchmark import BenchmarkSuite
from ..cirq_rag_code_assistant.config.logging import get_logger

logger = get_logger(__name__)


class ReportGenerator:
    """Generates evaluation reports."""

    def __init__(
        self,
        output_dir: Optional[Path] = None,
    ):
        self.output_dir = Path(output_dir) if output_dir else Path("outputs/reports")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized ReportGenerator with output dir: {self.output_dir}")

    def generate_report(
        self,
        metrics: Optional[MetricsCollector] = None,
        benchmark_results: Optional[Dict[str, Any]] = None,
        format: str = "json",
    ) -> Path:
        """Generate an evaluation report."""
        report = {
            "timestamp": datetime.now().isoformat(),
            "stack": {
                "provider": "aws",
                "note": "AWS Bedrock — see config/config.json for per-agent Claude models",
                "rag_top_k": 5,
                "rl_training": False,
            },
            "metrics": metrics.get_aggregated_metrics() if metrics else {},
            "benchmark_results": benchmark_results or {},
        }

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"evaluation_report_{timestamp}.{format}"
        filepath = self.output_dir / filename

        if format == "json":
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2, default=str)
        else:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(self._format_text_report(report))

        logger.info(f"Generated report: {filepath}")
        return filepath

    def _format_text_report(self, report: Dict[str, Any]) -> str:
        """Format report as text with CI columns."""
        lines = [
            "=" * 70,
            "Evaluation Report — Cirq RAG Code Assistant",
            "=" * 70,
            f"Timestamp: {report['timestamp']}",
            f"Provider: {report.get('stack', {}).get('provider', 'aws')} (Bedrock)",
            f"RL training active: {report.get('stack', {}).get('rl_training', False)}",
            "",
        ]

        if report.get("metrics"):
            lines.extend(["Metrics:", "-" * 70])
            metrics = report["metrics"]
            if "code_quality" in metrics:
                qm = metrics["code_quality"]
                lines.extend([
                    "  Code Quality:",
                    f"    Total Samples: {qm.get('total_samples', 0)}",
                    f"    Avg Code Length: {qm.get('avg_code_length', 0):.0f}",
                    f"    Syntax Valid Rate: {qm.get('syntax_valid_rate', 0):.1%}",
                    f"    Compilation Success Rate: {qm.get('compilation_success_rate', 0):.1%}",
                    f"    Code Quality Score: {qm.get('avg_code_quality_score', 0):.3f} "
                    f"± {qm.get('code_quality_std', 0):.3f} "
                    f"[95% CI: {qm.get('code_quality_ci_lower', 0):.3f}, "
                    f"{qm.get('code_quality_ci_upper', 0):.3f}]",
                ])
            lines.append("")

        br = report.get("benchmark_results") or {}
        if br:
            lines.extend(["Benchmark Results:", "-" * 70])

            if "per_prompt" in br:
                lines.extend([
                    f"  Multi-trial: {br.get('num_trials_per_prompt', '?')} trials × "
                    f"{br.get('total_prompts', '?')} prompts = {br.get('total_runs', '?')} runs",
                    f"  Overall Pass Rate: {br.get('overall_pass_rate', 0):.1%}",
                ])
                oci = br.get("overall_pass_rate_ci", {})
                if oci:
                    lines.append(
                        f"    95% CI: [{oci.get('ci_lower', 0):.1%}, {oci.get('ci_upper', 0):.1%}]"
                    )
                lines.append("")
                lines.append(f"  {'ID':<12} {'Tier':<14} {'Success':<12} {'Latency (s)':<22} {'Quality':<12}")
                lines.append("  " + "-" * 66)
                for p in br.get("per_prompt", []):
                    sr = p.get("success_rate", 0)
                    ci = p.get("success_rate_ci", {})
                    lat = p.get("latency_stats", {})
                    qual = p.get("code_quality_stats", {})
                    lines.append(
                        f"  {p.get('test_id', ''):<12} {p.get('tier', ''):<14} "
                        f"{sr:.1%} [{ci.get('ci_lower', 0):.1%},{ci.get('ci_upper', 0):.1%}]  "
                        f"{lat.get('mean', 0):.1f}±{lat.get('std', 0):.1f}  "
                        f"{qual.get('mean', 0):.3f}±{qual.get('std', 0):.3f}"
                    )
            else:
                lines.extend([
                    f"  Total Tests: {br.get('total_tests', 0)}",
                    f"  Passed: {br.get('passed', 0)}",
                    f"  Failed: {br.get('failed', 0)}",
                    f"  Pass Rate: {br.get('pass_rate', 0):.1%}",
                ])
                for tr in br.get("test_results", []):
                    lines.append(
                        f"    [{tr.get('tier', '?')}] {tr.get('test_id')}: "
                        f"{'PASS' if tr.get('success') and tr.get('validation_passed') else 'FAIL'} "
                        f"({tr.get('latency_seconds', 0):.1f}s, "
                        f"quality={tr.get('code_quality_score', 0):.2f})"
                    )

        lines.append("=" * 70)
        return "\n".join(lines)
