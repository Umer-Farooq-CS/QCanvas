"""
CLI Commands Module

This module implements individual CLI commands.
"""

from pathlib import Path
from typing import Optional
import click

from ..rag.embeddings import EmbeddingModel
from ..rag.vector_store import VectorStore
from ..rag.knowledge_base import KnowledgeBase
from ..rag.retriever import Retriever
from ..rag.generator import Generator
from ..agents.designer import DesignerAgent
from ..agents.optimizer import OptimizerAgent
from ..agents.validator import ValidatorAgent
from ..agents.educational import EducationalAgent
from ..orchestration.orchestrator import Orchestrator
from ..cirq_rag_code_assistant.config.logging import get_logger
from ..cirq_rag_code_assistant.config import get_config

logger = get_logger(__name__)


# Global orchestrator instance (lazy initialization)
_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    """Get or create orchestrator instance."""
    global _orchestrator
    
    if _orchestrator is None:
        # Get config
        config = get_config()
        
        # Initialize components
        embedding_model = EmbeddingModel()

        # Read vector store type from config (set by CIRQ_RAG_VECTOR_STORE_TYPE env var).
        vs_type = config.get("rag", {}).get("vector_store", {}).get("type", "faiss")
        vector_store = VectorStore(
            embedding_model.get_embedding_dimension(),
            vector_db_type=vs_type,
        )
        knowledge_base = KnowledgeBase(
            embedding_model=embedding_model,
            vector_store=vector_store,
        )
        
        # Load knowledge base if available
        try:
            knowledge_base.load_from_directory()
            knowledge_base.load_index()
        except Exception as e:
            logger.warning(f"Could not load knowledge base: {e}")
        
        retriever = Retriever(knowledge_base)
        generator = Generator(retriever)
        
        # Initialize agents
        designer = DesignerAgent(retriever, generator)
        optimizer = OptimizerAgent()
        validator = ValidatorAgent()
        educational = EducationalAgent(retriever)
        
        # Create orchestrator
        _orchestrator = Orchestrator(
            designer=designer,
            optimizer=optimizer,
            validator=validator,
            educational=educational,
        )
    
    return _orchestrator


def generate_command(
    query: str,
    algorithm: Optional[str],
    optimize: bool,
    validate: bool,
    explain: bool,
    output: Optional[str],
):
    """Generate code command."""
    click.echo(f"Generating code for: {query}")
    
    orchestrator = get_orchestrator()
    result = orchestrator.generate_code(
        query=query,
        algorithm=algorithm,
        optimize=optimize,
        validate=validate,
        explain=explain,
    )
    
    if result.get("success"):
        code = result.get("optimized_code") or result.get("code")
        click.echo("\n✅ Code generated successfully!\n")
        click.echo("=" * 60)
        click.echo(code)
        click.echo("=" * 60)
        
        if output:
            Path(output).write_text(code)
            click.echo(f"\n💾 Saved to: {output}")
    else:
        click.echo("\n❌ Code generation failed!")
        for error in result.get("errors", []):
            click.echo(f"  - {error}")


def optimize_command(code_file: str, level: str, output: Optional[str]):
    """Optimize code command."""
    click.echo(f"Optimizing code from: {code_file}")
    
    code = Path(code_file).read_text()
    orchestrator = get_orchestrator()
    
    result = orchestrator.optimizer.run({
        "code": code,
        "optimization_level": level,
    })
    
    if result.get("success"):
        optimized_code = result.get("optimized_code")
        click.echo("\n✅ Code optimized successfully!\n")
        click.echo(optimized_code)
        
        if output:
            Path(output).write_text(optimized_code)
            click.echo(f"\n💾 Saved to: {output}")
    else:
        click.echo(f"\n❌ Optimization failed: {result.get('error')}")


def validate_command(code_file: str, level: str):
    """Validate code command."""
    click.echo(f"Validating code from: {code_file}")
    
    code = Path(code_file).read_text()
    orchestrator = get_orchestrator()
    
    result = orchestrator.validator.run({
        "code": code,
        "validation_level": level,
    })
    
    if result.get("validation_passed"):
        click.echo("\n✅ Code validation passed!")
    else:
        click.echo("\n❌ Code validation failed!")
        for error in result.get("errors", []):
            click.echo(f"  - {error}")


def explain_command(code_file: str, depth: str, algorithm: Optional[str]):
    """Explain code command."""
    click.echo(f"Generating explanation for: {code_file}")
    
    code = Path(code_file).read_text()
    orchestrator = get_orchestrator()
    
    result = orchestrator.educational.run({
        "code": code,
        "depth": depth,
        "algorithm": algorithm,
    })
    
    if result.get("success"):
        explanations = result.get("explanations", {})
        click.echo("\n📚 Explanation:\n")
        click.echo(explanations.get("overview", ""))
        click.echo("\nStep-by-step:")
        for step in explanations.get("step_by_step", []):
            click.echo(f"  {step}")
    else:
        click.echo(f"\n❌ Explanation generation failed: {result.get('error')}")


def benchmark_command(output: Optional[str], trials: int = 1):
    """Run benchmarks command."""
    from ..evaluation.benchmark import BenchmarkSuite, load_benchmark_prompts
    from ..evaluation.metrics import MetricsCollector
    from ..evaluation.reports import ReportGenerator

    prompts = load_benchmark_prompts(exclude_explanation=True)
    click.echo(
        f"Running benchmarks ({len(prompts)} prompts, "
        f"AWS Bedrock per config/config.json)..."
    )
    if trials > 1:
        click.echo(f"  Multi-trial mode: {trials} trials per prompt")

    orchestrator = get_orchestrator()
    benchmark_suite = BenchmarkSuite(orchestrator, MetricsCollector())

    if trials > 1:
        results = benchmark_suite.run_benchmarks_multi_trial(num_trials=trials)
        click.echo(f"\n✅ Benchmarks completed ({results['total_runs']} total runs)!")
        click.echo(f"  Overall Pass Rate: {results['overall_pass_rate']:.1%}")
        oci = results.get("overall_pass_rate_ci", {})
        if oci:
            click.echo(
                f"  95% CI: [{oci.get('ci_lower', 0):.1%}, {oci.get('ci_upper', 0):.1%}]"
            )
    else:
        results = benchmark_suite.run_benchmarks(test_cases=prompts)
        click.echo(f"\n✅ Benchmarks completed!")
        click.echo(f"  Passed: {results['passed']}/{results['total_tests']}")
        click.echo(f"  Pass Rate: {results['pass_rate']:.1%}")

    if output:
        report_generator = ReportGenerator()
        report_path = report_generator.generate_report(
            metrics=benchmark_suite.metrics_collector,
            benchmark_results=results,
            format="json" if str(output).endswith(".json") else "text",
        )
        click.echo(f"\n💾 Report saved to: {report_path}")
