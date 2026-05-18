"""One-off script to update notebooks 12, 13, 14 for benchmark v2 alignment."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def set_cell_source(nb, idx: int, source: str) -> None:
    nb["cells"][idx]["source"] = source.splitlines(keepends=True)
    nb["cells"][idx]["outputs"] = []
    nb["cells"][idx]["execution_count"] = None


def update_notebook_12() -> None:
    path = ROOT / "notebooks" / "12_visualization.ipynb"
    nb = json.loads(path.read_text(encoding="utf-8"))

    set_cell_source(
        nb,
        0,
        """# 12. Visualization Notebook

Visualizes system performance from **live ablation benchmarks** (not hardcoded values).

## Production stack (AWS Bedrock)
| Agent | Model |
|-------|-------|
| Designer / Validator | `anthropic.claude-sonnet-4-6` |
| Optimizer | `anthropic.claude-opus-4-6-v1` (`use_rl: false`) |
| Educational | `anthropic.claude-haiku-4-5-20251001-v1:0` |
| Embeddings | `amazon.nova-2-multimodal-embeddings-v1:0` |

- **25 prompts** in `data/datasets/benchmark_prompts_v2.jsonl` (code tiers only for ablation)
- **RAG:** top_k=5, similarity_threshold=0.7
""",
    )

    set_cell_source(
        nb,
        5,
        """## 3. System Mode Comparison

Runs `AblationStudy` across six variants on the v2 benchmark suite.
Results are cached to `results/ablation_results.json` — delete that file to force a re-run.

**Note:** Full 25-prompt × 6-variant runs are expensive (AWS Bedrock). Use `MAX_BENCHMARK_CASES`
for a subset during development.""",
    )

    set_cell_source(
        nb,
        6,
        '''# Run ablation study (or load cached results)
import json
from src.evaluation.ablation import AblationStudy, VARIANT_LABELS
from src.evaluation.benchmark import load_benchmark_prompts

# --- Configuration ---
RUN_ABLATION = True          # Set False to only load cached results
MAX_BENCHMARK_CASES = 5      # None = all 25 code prompts; use 5 for quick dev runs
ABLATION_CACHE = results_dir / "ablation_results.json"

benchmark_cases = load_benchmark_prompts(exclude_explanation=True)
print(f"Benchmark prompts loaded: {len(benchmark_cases)} (code tiers only)")

if RUN_ABLATION:
    study = AblationStudy(benchmark_cases=benchmark_cases)
    variants = list(VARIANT_LABELS.keys())
    print(f"Running ablation: {len(variants)} variants × {MAX_BENCHMARK_CASES or len(benchmark_cases)} prompts...")
    ablation_raw = study.run_study(variants=variants, max_cases=MAX_BENCHMARK_CASES)
    study.save_results(ABLATION_CACHE, ablation_raw)
else:
  if ABLATION_CACHE.exists():
    ablation_raw = AblationStudy.load_results(ABLATION_CACHE)
    study = AblationStudy()
    study.results = ablation_raw
  else:
    raise FileNotFoundError(f"No cache at {ABLATION_CACHE}; set RUN_ABLATION=True")

modes = study.aggregate_to_modes_dict(ablation_raw if RUN_ABLATION else study.results)
mode_names = list(modes.keys())

print(f"\\n📊 Comparing {len(mode_names)} system modes (from benchmarks)")
for name in mode_names:
    m = modes[name]
    print(f"\\n{name}:")
    print(f"  Components: {', '.join(m['components'])}")
    print(f"  Success: {m['success_rate']:.1%} | Validation: {m['validation_rate']:.1%} | "
          f"Latency: {m['avg_latency']:.1f}±{m['latency_std']:.1f}s | Quality: {m['code_quality']:.2f}")
''',
    )

    set_cell_source(
        nb,
        7,
        """### 3.1 Performance Metrics Overview

**Code Quality Formula (published, §4.3):**
```
CodeQuality(c) = 0.30 × SyntaxValid(c)
              + 0.30 × CompilationSuccess(c)
              + 0.20 × HasMeasurement(c)
              + 0.10 × CircuitNonEmpty(c)
              + 0.10 × CorrectImports(c)
```

Values come from `compute_code_quality_score()` during each benchmark run — not re-derived in plots.""",
    )

    # Cell 8: remove recalculation block — keep only plotting
    cell8 = '''# Performance metrics from benchmark-derived `modes` dict
success_rates = [modes[n]["success_rate"] for n in mode_names]
validation_rates = [modes[n]["validation_rate"] for n in mode_names]
code_qualities = [modes[n]["code_quality"] for n in mode_names]
latencies = [modes[n]["avg_latency"] for n in mode_names]
latency_stds = [modes[n]["latency_std"] for n in mode_names]
depths = [modes[n]["circuit_depth"] for n in mode_names]
num_gates = [modes[n]["num_gates"] for n in mode_names]
two_qubit = [modes[n]["two_qubit_gates"] for n in mode_names]
code_lengths = [modes[n]["code_length"] for n in mode_names]

print("✅ Using benchmark-derived code quality scores (published formula)")

# Performance metrics - Success Rate
'''
    # Read rest of cell 8 from file - use grep to get plotting code starting at fig, ax
    old8 = "".join(nb["cells"][8]["source"])
    marker = "# Performance metrics - Success Rate"
    if marker in old8:
        plotting_part = old8[old8.index(marker):]
        set_cell_source(nb, 8, cell8 + plotting_part)
    else:
        set_cell_source(nb, 8, cell8 + old8)

    set_cell_source(
        nb,
        19,
        """## 5. Summary

- **Modes dict** is built from `AblationStudy` on `benchmark_prompts_v2.jsonl` (AWS Bedrock).
- **Code quality** uses the published weighted binary formula in `metrics.py`.
- Increase `MAX_BENCHMARK_CASES` to `None` and set `RUN_ABLATION=True` for full paper runs.
- See `BENCHMARK.md` for CLI and multi-trial (`n=5`) instructions.""",
    )

    path.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Updated {path}")


def update_notebook_13() -> None:
    path = ROOT / "notebooks" / "13_api_testing.ipynb"
    nb = json.loads(path.read_text(encoding="utf-8"))

    set_cell_source(
        nb,
        0,
        """# 13. API Testing Notebook

Tests internal APIs including the **v2 benchmark suite** and evaluation metrics.
Stack: AWS Bedrock (see `config/config.json`).""",
    )

    # Insert evaluation tests before summary (cell 5)
    eval_cell = '''print("\\n" + "=" * 50)
print("📊 EVALUATION & BENCHMARK TESTS")
print("=" * 50)

from src.evaluation.benchmark import load_benchmark_prompts, STANDARD_BENCHMARKS
from src.evaluation.metrics import compute_code_quality_score, compute_statistics, wilson_ci

run_test("load_benchmark_prompts", lambda: len(load_benchmark_prompts()) == 25)
run_test("exclude_explanation tier", lambda: len(load_benchmark_prompts(exclude_explanation=True)) == 20)
run_test("STANDARD_BENCHMARKS fallback", lambda: len(STANDARD_BENCHMARKS) >= 4)

sample_code = "import cirq\\nq = cirq.LineQubit.range(2)\\nc = cirq.Circuit(cirq.H(q[0]), cirq.measure(q[0], key='m'))"
validation = {"compilation": {"success": True, "circuit": None}, "validation_passed": True}
score = compute_code_quality_score(sample_code, validation)
run_test("compute_code_quality_score", lambda: 0 <= score["code_quality_score"] <= 1)

stats = compute_statistics([0.8, 0.9, 0.85, 0.88, 0.92])
run_test("compute_statistics", lambda: stats["n"] == 5 and stats["mean"] > 0)

ci = wilson_ci(8, 10)
run_test("wilson_ci", lambda: 0 <= ci["ci_lower"] <= ci["mean"] <= ci["ci_upper"] <= 1)

from src.evaluation.ablation import AblationStudy, VARIANT_LABELS
run_test("AblationStudy import", lambda: len(VARIANT_LABELS) == 6)
'''
    nb["cells"].insert(5, {"cell_type": "code", "metadata": {}, "source": eval_cell.splitlines(keepends=True), "outputs": [], "execution_count": None})

    path.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Updated {path}")


def update_notebook_14() -> None:
    path = ROOT / "notebooks" / "14_cli_testing.ipynb"
    nb = json.loads(path.read_text(encoding="utf-8"))

    set_cell_source(
        nb,
        0,
        """# 14. CLI Testing Notebook

Tests CLI commands. Benchmarks use **25 prompts** from `benchmark_prompts_v2.jsonl`
via AWS Bedrock (`config/config.json`).""",
    )

    benchmark_cell = '''print("\\n📊 BENCHMARK CLI (subset — use --trials 5 for paper stats)")
print("Listing benchmark prompts...")
from src.evaluation.benchmark import load_benchmark_prompts
prompts = load_benchmark_prompts(exclude_explanation=True)
print(f"  {len(prompts)} code-generation prompts loaded")
for p in prompts[:3]:
    print(f"  - [{p['tier']}] {p['id']}: {p['query'][:60]}...")

# Quick dry-run help (full run is expensive):
print("\\nTo run full benchmark:")
print("  python src/cli/main.py benchmark --output outputs/reports/benchmark.json")
print("  python src/cli/main.py benchmark --trials 5 --output outputs/reports/benchmark_multi.json")
'''
    nb["cells"].insert(12, {"cell_type": "code", "metadata": {}, "source": benchmark_cell.splitlines(keepends=True), "outputs": [], "execution_count": None})

    summary_idx = 13
    old_summary = "".join(nb["cells"][summary_idx]["source"])
    set_cell_source(
        nb,
        summary_idx,
        old_summary.replace(
            "  python src/cli/main.py benchmark --output report.txt",
            "  python src/cli/main.py benchmark --output report.json\n"
            "  python src/cli/main.py benchmark --trials 5 --output report_multi.json",
        ),
    )

    path.write_text(json.dumps(nb, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"Updated {path}")


if __name__ == "__main__":
    update_notebook_12()
    update_notebook_13()
    update_notebook_14()
