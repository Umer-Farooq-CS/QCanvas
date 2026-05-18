"""
Evaluation Module

This module implements the evaluation framework for assessing
code generation quality, agent performance, and system metrics.

Author: Umer Farooq, Hussain Waseem Syed, Muhammad Irtaza Khan
Email: umerfarooqcs0891@gmail.com
"""

# This file will export evaluation components
from .metrics import (
    MetricsCollector,
    compute_code_quality_score,
    compute_statistics,
    wilson_ci,
)
from .benchmark import (
    BenchmarkSuite,
    load_benchmark_prompts,
    sample_benchmark_cases,
    get_validation_from_result,
    STANDARD_BENCHMARKS,
)
from .ablation import AblationStudy, VARIANT_LABELS, VARIANT_COMPONENTS
from .reports import ReportGenerator

__all__ = [
    "MetricsCollector",
    "compute_code_quality_score",
    "compute_statistics",
    "wilson_ci",
    "BenchmarkSuite",
    "load_benchmark_prompts",
    "sample_benchmark_cases",
    "get_validation_from_result",
    "STANDARD_BENCHMARKS",
    "AblationStudy",
    "VARIANT_LABELS",
    "VARIANT_COMPONENTS",
    "ReportGenerator",
]

