# Benchmark Suite Guide

The Cirq RAG Code Assistant evaluation uses **25 reproducible prompts** in
`data/datasets/benchmark_prompts_v2.jsonl`, aligned with the paper revision plan.

## Prompt tiers

| Tier | Count | Examples |
|------|-------|----------|
| basic | 5 | Bell state, GHZ, swap test |
| intermediate | 5 | Grover, QFT, teleportation |
| algorithm | 5 | VQE (4-qubit), QAOA, Deutsch-Jozsa |
| advanced | 5 | QSVT, quantum walk, amplitude estimation |
| explanation | 5 | Hadamard superposition, Grover oracle vs diffusion |

## Production stack (AWS Bedrock)

Experiments should use the providers configured in `config/config.json`:

- **Designer / Validator:** `anthropic.claude-sonnet-4-6`
- **Optimizer:** `anthropic.claude-opus-4-6-v1` (`use_rl: false` — reward weights are scoring only)
- **Educational:** `anthropic.claude-haiku-4-5-20251001-v1:0`
- **Embeddings:** `amazon.nova-2-multimodal-embeddings-v1:0` (1024-dim)
- **RAG:** `top_k_results=5`, `similarity_threshold=0.7`

## Running benchmarks

```bash
# Single trial (all 25 prompts)
python -m src.cli.main benchmark --output outputs/reports/benchmark.json

# From Python
from src.evaluation.benchmark import BenchmarkSuite, load_benchmark_prompts
from src.evaluation.metrics import MetricsCollector

prompts = load_benchmark_prompts()
suite = BenchmarkSuite(orchestrator, MetricsCollector())
results = suite.run_benchmarks(test_cases=prompts)

# Multi-trial (n=5 per prompt, for paper statistics)
multi = suite.run_benchmarks_multi_trial(num_trials=5)
```

## Running the full ablation study (recommended for paper)

1. Ensure your environment is activated and dependencies are installed (includes `scipy`):

```bash
python -m pip install -r requirements-dev.txt
```

2. Configure provider (local Ollama or AWS Bedrock) in `config/config.json`. If using AWS, ensure credentials are available.

3. Run the ablation study notebook or use the CLI to run the full multi-trial evaluation:

```bash
# Run Notebook 15 step2 (open in Jupyter and set NUM_TRIALS=5, RUN_ABLATION=True)
# OR use the CLI wrapper if present:
python -m src.cli.main ablation --num-trials 5 --output results/ablation_results_step2.json
```

4. After completion, verify the generated files:

- `results/ablation_results_step2.json` — raw per-trial details
- `results/ablation_summary_step2.csv` — aggregated summary for paper tables
- `results/step2_statistical_comparisons.csv` — McNemar and paired t-test results

## How to confirm correctness (logical & semantic)

1. Unit tests: run `pytest` to ensure APIs behave as expected:

```bash
pytest -q
```

2. Sanity checks on outputs:

- Ensure each entry in `ablation_results_step2.json` has `details` length = `num_trials * num_cases` per variant.
- Check `success_rate` and `validation_rate` lie between 0 and 1 and CI bounds are sane.

3. Semantic validation of generated code (per-trial):

- Use `src/evaluation/metrics.assess_code_objectively()` to confirm `validation_passed` is True for expected cases.
- Spot-check circuits by loading `results/ablation_results_step2.json` and compiling the `code` field with `CirqCompiler().compile(code, execute=True)`; ensure compilation `success==True`.

4. Reproducibility checks:

- Re-run 2–3 random prompts and confirm metrics vary within computed CI ranges. Large deviations indicate non-deterministic provider behaviour or changed model config.

5. Human spot-check:

- Manually review a sample of generated circuits for semantic correctness (use the notebook `12_visualization.ipynb` or the new `15_step2_multi_trial.ipynb` to inspect `details`).

If you want, I can add automated unit tests that compile every generated code snippet in the results file and report failures.

## Code quality formula

```
CodeQuality(c) = 0.30 × SyntaxValid(c)
              + 0.30 × CompilationSuccess(c)
              + 0.20 × HasMeasurement(c)
              + 0.10 × CircuitNonEmpty(c)
              + 0.10 × CorrectImports(c)
```

All components are binary (0 or 1). See `src/evaluation/metrics.py`.

## Ablation variants

| Variant key | Description |
|-------------|-------------|
| `full` | RAG + Designer + Validator + Optimizer + Final Validator |
| `no_rag` | Designer without RAG context |
| `no_validator` | Skip initial validation |
| `no_optimizer` | Skip optimization |
| `no_final_validator` | Skip final validation pass |
| `minimal` | Designer only |

## Notebooks

- **10_evaluation.ipynb** — Full benchmark + ablation runs
- **12_visualization.ipynb** — Plots from live ablation results (or cached JSON)
- **13_api_testing.ipynb** — Unit tests for evaluation APIs
- **14_cli_testing.ipynb** — CLI including `benchmark` command

## Local reproduction (Ollama fallback)

Readers without AWS credentials can switch agent providers to `ollama` in
`config/config.json` and use `qwen2.5-coder:14b-instruct-q4_K_M`. Results will
differ from the production Bedrock numbers reported in the paper.
