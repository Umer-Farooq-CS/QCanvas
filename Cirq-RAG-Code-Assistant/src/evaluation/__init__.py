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
from .reports import ReportGenerator

__all__ = [
    "MetricsCollector",
    "compute_code_quality_score",
    "compute_statistics",
    "wilson_ci",
    "ReportGenerator",
]

