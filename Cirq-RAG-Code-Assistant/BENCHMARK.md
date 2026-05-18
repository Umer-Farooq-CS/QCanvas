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
