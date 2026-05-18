"""
CLI Main Module

This module implements the main CLI entry point.
"""

import click
from pathlib import Path
from .commands import (
    generate_command,
    optimize_command,
    validate_command,
    explain_command,
    benchmark_command,
)
from ..cirq_rag_code_assistant.config.logging import setup_default_logging

# Setup logging
setup_default_logging()


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Cirq-RAG-Code-Assistant CLI."""
    pass


@cli.command()
@click.argument("query")
@click.option("--algorithm", help="Algorithm type (vqe, qaoa, grover, etc.)")
@click.option("--optimize/--no-optimize", default=True, help="Optimize generated code")
@click.option("--validate/--no-validate", default=True, help="Validate generated code")
@click.option("--explain/--no-explain", default=True, help="Generate explanations")
@click.option("--output", type=click.Path(), help="Output file path")
def generate(query, algorithm, optimize, validate, explain, output):
    """Generate Cirq code from natural language query."""
    generate_command(query, algorithm, optimize, validate, explain, output)


@cli.command()
@click.argument("code_file", type=click.Path(exists=True))
@click.option("--level", default="balanced", help="Optimization level (conservative, balanced, aggressive)")
@click.option("--output", type=click.Path(), help="Output file path")
def optimize(code_file, level, output):
    """Optimize a Cirq circuit."""
    optimize_command(code_file, level, output)


@cli.command()
@click.argument("code_file", type=click.Path(exists=True))
@click.option("--level", default="comprehensive", help="Validation level (basic, comprehensive)")
def validate(code_file, level):
    """Validate Cirq code."""
    validate_command(code_file, level)


@cli.command()
@click.argument("code_file", type=click.Path(exists=True))
@click.option("--depth", default="intermediate", help="Explanation depth (beginner, intermediate, advanced)")
@click.option("--algorithm", help="Algorithm type")
def explain(code_file, depth, algorithm):
    """Generate educational explanations for code."""
    explain_command(code_file, depth, algorithm)


@cli.command()
@click.option("--output", type=click.Path(), help="Output report file path")
@click.option("--trials", default=1, type=int, help="Number of trials per prompt (default: 1)")
def benchmark(output, trials):
    """Run benchmark tests (25 prompts from benchmark_prompts_v2.jsonl)."""
    benchmark_command(output, trials=trials)


def main():
    """Main CLI entry point."""
    cli()


if __name__ == "__main__":
    main()
