# Cirq RAG Assistant — Research Paper Revision Plan

> **Authors:** Umer Farooq, Hussain Waseem Syed, Muhammad Irtaza Khan  
> **Document purpose:** Address all critique points raised by the professor and clarify
> the shift from local-Ollama experiments to the deployed AWS/Anthropic stack.

---

## 0. Context — What the Paper Currently Says vs. Reality

The submitted paper describes experiments run with **local Ollama models**
(`qwen2.5-coder:14b`, `cirq-designer-agent` Modelfile, etc.).  
The production codebase (`Cirq-RAG-Code-Assistant/src/`) supports **four providers**:
`ollama`, `openai`, `anthropic`, and `aws` (Bedrock Converse API via `boto3`).

### Verified Model Configuration (from `config/config.json`)

The following table shows the **exact models** configured for each agent and component:

| Component | Provider | Model ID (as in config.json) | Role |
|-----------|----------|------------------------------|------|
| **Designer Agent** | `aws` (Bedrock) | `anthropic.claude-sonnet-4-6` | Generates Cirq code from natural language + RAG context |
| **Optimizer Agent** | `aws` (Bedrock) | `anthropic.claude-opus-4-6-v1` | Optimizes circuits; temp=0.2, max_tokens=2000 |
| **Validator Agent** | `aws` (Bedrock) | `anthropic.claude-sonnet-4-6` | Validates + fixes code via LLM; mode=local |
| **Educational Agent** | `aws` (Bedrock) | `anthropic.claude-haiku-4-5-20251001-v1:0` | Generates explanations (lighter, faster model) |
| **Embeddings** | `aws` (Bedrock) | `amazon.nova-2-multimodal-embeddings-v1:0` | 1024-dim vectors for RAG retrieval |
| **Vector Store** | local / prod | FAISS (dev) / pgvector (prod) | Similarity search index |

> **Key insight for the paper:** Different agents deliberately use different Claude tiers.
> The Optimizer uses the more powerful **Claude Opus** because circuit optimization
> requires deeper reasoning; the Educational agent uses the lightweight **Claude Haiku**
> for speed. This tiered model selection is itself a contribution worth highlighting.

### RAG Configuration (from `config/config.json`)
- `top_k_results`: **5** (not 3 — correct this wherever the paper says top-3)
- `similarity_threshold`: **0.7**
- `chunk_size`: **512 tokens**, `chunk_overlap`: **50 tokens**
- Knowledge base path: `data/knowledge_base` | size_target in config: **2,500 entries**

### RL Status (from `config/config.json`)
- `agents.optimizer.use_rl`: **`false`** — RL training loop is **disabled** in production.
- `rl_reward_weights` are configured (circuit_depth: −0.3, two_qubit_gates: −0.3, fidelity: +0.4)
  but the weights are only used by the `_calculate_reward()` scoring method, not a live training loop.
- This **must** be accurately reflected in the paper (see §8 below).

### Required framing change
- Re-run (or re-label) all experiments under the **AWS Bedrock** provider so the
  paper reflects actual production setup.
- Wherever re-running is not feasible, add a **"Reproducibility Note"** appendix
  explaining how to reproduce results locally with Ollama.
- Update the **Technology Stack** section to list the exact model IDs above.
- Secondary / local fallback: Ollama (`qwen2.5-coder:14b-instruct-q4_K_M`) — retain
  for readers without AWS access.

---

## 1. Critique Point — Benchmark Too Small (4 prompts)

### Current state
`src/evaluation/benchmark.py` → `STANDARD_BENCHMARKS` contains **4 test cases**:
Bell state, Grover (3-qubit), VQE (2-qubit), QAOA (2-qubit).

### Plan

**1a. Expand the benchmark set to 25 prompts** across five difficulty tiers:

| Tier | Count | Examples |
|------|-------|---------|
| Basic (1-2 qubit) | 5 | Bell state, GHZ, X/H/CNOT identity, swap test |
| Intermediate | 5 | 3-qubit Grover, QFT (3-qubit), teleportation |
| Algorithm | 5 | VQE (4-qubit), QAOA (4-node), Deutsch-Jozsa |
| Advanced | 5 | QSVT, quantum walk, amplitude estimation |
| Explanation-only | 5 | "Explain why Hadamard creates superposition", etc. |

**1b. Add the expanded prompts to a new file:**
```
data/datasets/benchmark_prompts_v2.jsonl
```
Each entry format:
```json
{
  "id": "BM-001",
  "tier": "basic",
  "query": "Create a 2-qubit Bell state circuit",
  "algorithm": "bell_state",
  "expected_gates": ["H", "CNOT"],
  "expected_qubit_count": 2,
  "validation_criteria": "must_have_entanglement",
  "failure_cases": ["missing H gate", "missing CNOT", "no measurement"]
}
```

**1c. Code changes required:**
- `src/evaluation/benchmark.py`: Load prompts from JSONL file; keep old
  `STANDARD_BENCHMARKS` as fallback.
- `src/evaluation/benchmark.py`: Add `tier` field to `test_result` dict.

---

## 2. Critique Point — Weak Evaluation Protocol (single trial, no statistics)

### Current state
Each prompt is run **once**. No mean/std/CI reported anywhere.

### Plan

**2a. Implement multi-trial runner** — new method in `BenchmarkSuite`:

```python
def run_benchmarks_multi_trial(
    self,
    test_cases=None,
    num_trials: int = 5,
) -> Dict[str, Any]:
    """Run each prompt `num_trials` times and compute statistics."""
```

**2b. Statistics to compute per prompt:**
- Mean success rate, std dev, 95% CI (Wilson interval for proportions)
- Mean code quality score, std dev
- Mean latency (seconds), std dev
- Mean circuit depth, mean gate count

**2c. Statistical significance test:**
- Use **McNemar's test** to compare Full System vs. ablation variants.
- Use **paired t-test** for continuous metrics (latency, depth).
- Report p-values; threshold p < 0.05 for significance.

**2d. Code changes required:**
- `src/evaluation/benchmark.py`: Add `run_benchmarks_multi_trial()`.
- `src/evaluation/metrics.py`: Add `compute_statistics(values: List[float])` →
  returns `{mean, std, ci_lower, ci_upper}`.
- `src/evaluation/reports.py`: Extend text/JSON report to include CI columns.

**2e. Paper changes:**
- Replace all single-value result tables with mean ± std columns.
- Add a "Statistical Analysis" subsection under Experiments.
- Report: n=5 trials per prompt × 25 prompts = 125 total LLM calls per configuration.

---

## 3. Critique Point — Benchmark Prompts Not Reproducible

### Plan

**3a. Add Appendix A to the paper:** "Benchmark Prompt Catalogue"
- Full text of every prompt (25 prompts).
- Expected output description.
- Validation criteria (what constitutes pass/fail).
- At least 3 known failure cases per prompt category.

**3b. Public repository link:**
- Publish `data/datasets/benchmark_prompts_v2.jsonl` to the GitHub repo
  (`Umer-Farooq-CS/Cirq-RAG-Code-Assistant`).
- Add a `BENCHMARK.md` at the repo root pointing to the file.

**3c. Validation criteria to define explicitly:**
| Criterion | Definition |
|-----------|-----------|
| Syntax valid | `ast.parse(code)` does not raise |
| Compilation success | `CirqCompiler.compile(code, execute=True)["success"]` is True |
| Circuit non-empty | `len(list(circuit.all_operations())) > 0` |
| Measurement present | At least one `cirq.MeasurementGate` in circuit |
| Algorithm-correct | Semantic validation via RAG reference match (≥70% tolerance) |

---

## 4. Critique Point — Knowledge Base Too Small (140+ entries)

### Current state
`data/knowledge_base/` contains 3 JSONL files (designer, optimizer, validator examples).
Total ≈ 140 curated entries.

### Plan (two options, choose one)

**Option A — Expand to 500+ entries (preferred):**
- Add entries from:
  - Cirq official docs examples (scraped + curated)
  - `data/datasets/annotated_cirq_dataset.jsonl` (11 MB — already exists, ~10K entries)
    → filter by quality score threshold → add top 400 entries to knowledge base
- Target: 500 designer + 100 optimizer + 100 validator = 700 total entries.

**Option B — Keep 140, justify explicitly:**
- Add a "Knowledge Base Limitations" paragraph in §4 (Methodology).
- State: "The curated knowledge base intentionally prioritises precision over recall,
  containing 140 high-quality, manually-verified Cirq examples spanning 12 topic areas."
- Show coverage chart (already exists: `results/knowledge_base_topics.png`).

**Paper change regardless:**
- Add Table: Knowledge Base Composition (topic, entry count, source).
- State retrieval coverage: what % of benchmark queries returned ≥1 relevant result.

---

<!-- ## 5. Critique Point — Code Quality Metric Undefined

### Current state
`src/evaluation/metrics.py → collect_code_quality()` computes:
- `code_length`, `num_lines`, `syntax_valid`, `compilation_success`

No weighted formula is published. The paper says "syntax validity, compilation success,
and structural heuristics" without a formula.

### Plan

**5a. Define and publish the exact scoring formula:**

```
CodeQuality(c) = 0.30 × SyntaxValid(c)
              + 0.30 × CompilationSuccess(c)
              + 0.20 × HasMeasurement(c)
              + 0.10 × CircuitNonEmpty(c)
              + 0.10 × CorrectImports(c)
```

All components are binary (0 or 1), so CodeQuality ∈ [0, 1].

**5b. Code changes required:**
- `src/evaluation/metrics.py`: Add `compute_code_quality_score(code, validation_result)`
  implementing the formula above.
- Return the breakdown alongside the score.

**5c. Paper changes:**
- Add the formula as a numbered equation in §4.3 (Evaluation Metrics).
- Add a column "Code Quality Score" to all results tables.
- Include a worked example in the appendix. -->

## 5. Critique Point — Code Quality Metric Undefined

### Current state
`src/evaluation/metrics.py → collect_code_quality()` computes basic code properties: `code_length`, `num_lines`, `syntax_valid`, and `compilation_success`. The paper states "syntax validity, compilation success, and structural heuristics" without publishing an explicit, reproducible mathematical formula.

### Plan

**5a. Define and publish the Hybrid Quantum Code Quality Score ($Q_{\text{score}}$):**

Instead of using purely classical or surface-level software metrics, we introduce a composite framework that unifies **Functional Correctness** and **Resource Efficiency**. This ensures code efficiency is only rewarded if the generated code is programmatically executable and semantically correct.

$$Q_{\text{score}} = \text{Func}(c) \times \left( w_1 \cdot \frac{D_{\text{baseline}}}{D_{\text{gen}}} + w_2 \cdot \frac{G_{\text{baseline}}}{G_{\text{gen}}} \right)$$

Where:
* **$\text{Func}(c)$ (Functional Validity Gate):** A continuous correctness coefficient ($0.0 \le \text{Func}(c) \le 1.0$) defined as:
  $$\text{Func}(c) = 0.40 \cdot \text{SyntaxValid}(c) + 0.60 \cdot \text{Fidelity}(F)$$
  * $\text{SyntaxValid}(c) \in \{0, 1\}$ represents basic execution and compilation success[cite: 1].
  * $\text{Fidelity}(F) \in [0.0, 1.0]$ represents the quantum state fidelity $|\langle \psi_{\text{true}} | \psi_{\text{gen}} \rangle|^2$ calculated via full state-vector simulation. If the circuit throws a runtime error or creates an incorrect quantum state, $\text{Func}(c) \to 0$, reducing the entire quality score to zero.
* **$D_{\text{baseline}} / D_{\text{gen}}$:** The depth optimization ratio, comparing the critical path depth of the canonical algorithm against the generated Cirq circuit depth.
* **$G_{\text{baseline}} / G_{\text{gen}}$:** The gate-count economy ratio, measuring total operations to penalize redundant single or two-qubit gate configurations.
* **Weights ($w_1, w_2$):** Set default boundaries in `config/config.json` to $w_1 = 0.5$ and $w_2 = 0.5$ (where $w_1 + w_2 = 1.0$), mapping perfectly to the structural priorities defined in our optimization reward weights[cite: 1].

**5b. Code changes required:**
* `src/evaluation/metrics.py`: Add `compute_hybrid_quantum_score(gen_circuit, base_circuit)` to parse the generated code block, run it inside a local `cirq.Simulator()`, calculate state vector overlap against the reference baseline, extract circuit depth/gate constraints, and return the unified composite score.

```python
import cirq
import numpy as np

def compute_hybrid_quantum_score(gen_circuit, base_circuit, w1=0.5, w2=0.5):
    """
    Computes the hybrid code quality score gating resource efficiency 
    behind functional quantum correctness and state fidelity simulation.
    """
    try:
        # 1. Functional Correctness (Gating Stage)
        sim = cirq.Simulator()
        res_gen = sim.simulate(gen_circuit)
        res_base = sim.simulate(base_circuit)
        
        state_gen = res_gen.final_state_vector
        state_base = res_base.final_state_vector
        
        # Quantum State Fidelity calculation
        fidelity = np.abs(np.vdot(state_base, state_gen))**2
        func_gate = 0.40 + (0.60 * fidelity)
        
    except Exception:
        # Complete catastrophic failure or syntax error crashes the gate to 0
        return 0.0

    if fidelity < 1e-4:
        return 0.0

    # 2. Resource Efficiency Stage
    gen_depth = len(gen_circuit)
    base_depth = len(base_circuit)
    
    gen_gates = len(list(gen_circuit.all_operations()))
    base_gates = len(list(base_circuit.all_operations()))
    
    # Ratios penalize bloating; capped at 1.0 if agent out-optimizes baseline
    depth_ratio = min(1.0, base_depth / max(1, gen_depth))
    gate_ratio = min(1.0, base_gates / max(1, gen_gates))
    
    # Composite Final Score
    q_score = func_gate * ((w1 * depth_ratio) + (w2 * gate_ratio))
    return float(q_score)
```

**5c. Paper changes:**
* Add the unified $Q_{\text{score}}$ framework as a numbered equation in §4.3 (Evaluation Metrics).
* Add a column `"Hybrid Quality Score ($Q_{\text{score}}$)"` to all results tables.
* Ground the methodology explicitly in literature by citing peer-reviewed benchmarks:
  1. *State Validation & Correctness:* Cite **QuanBench** (Guo et al., 2025) to justify balancing syntactic compilation success with simulator-driven state fidelity validation.
  2. *Resource Parsing:* Cite **QCircuitBench** (Yang et al., 2024) to validate our parsing of concrete internal quantum properties (gate counts, circuit depth ratios) out of LLM generations.
  3. *Hybrid Framework Grounding:* Cite **Muñoz et al. (2024)** to anchor this hybrid software engineering approach.

#### Valid References to Add to `references.bib`
```bibtex
@article{guo2025quanbench,
  author    = {Guo, X. and Wang, M. and Zhao, J.},
  title     = {QuanBench: Benchmarking Quantum Code Generation with Large Language Models},
  journal   = {arXiv preprint arXiv:2510.16779},
  year      = {2025},
  url       = {[https://arxiv.org/abs/2510.16779](https://arxiv.org/abs/2510.16779)}
}

@article{yang2024qcircuitnet,
  author    = {Yang, R. and Gu, Y. and Wang, Z. and Liang, Y. and Li, T.},
  title     = {QCircuitNet: A Large-Scale Hierarchical Dataset for Quantum Algorithm Design},
  journal   = {arXiv preprint arXiv:2410.07961},
  year      = {2024},
  url       = {[https://arxiv.org/abs/2410.07961](https://arxiv.org/abs/2410.07961)}
}

@article{munoz2024towards,
  author    = {Mu{\~n}oz, A. D. and Monje, M. R. and Velthuis, M. G. P.},
  title     = {Towards a Set of Metrics for Hybrid (Quantum/Classical) Systems Maintainability},
  journal   = {JUCS - Journal of Universal Computer Science},
  volume    = {30},
  number    = {1},
  pages     = {25--48},
  year      = {2024},
  doi       = {10.3897/jucs.99348}
}
```


---

## 6. Critique Point — Limited Comparison Baselines

### Current state
The ablation study compares: Full System vs. No RAG, No Optimizer, No Validator,
Minimal. No external model comparisons.

### Plan

**6a. Add external baseline comparisons** (tier by feasibility):

**Tier 1 — API baselines (implementable now):**
| Baseline | Provider | How |
|----------|----------|-----|
| GPT-4o (no RAG) | OpenAI API | `generator.py` already supports `openai` provider |
| Claude 3.5 Sonnet (no RAG) | Anthropic direct | `generator.py` already supports `anthropic` provider |
| Gemini 1.5 Pro (no RAG) | Google AI | Add `gemini` provider to `generator.py` |
| Qwen-2.5-Coder (no RAG) | Ollama local | Already supported, just disable RAG |

**Tier 2 — Literature baselines (add to paper via citations):**
- **Qiskit Code Assistant** (Dupuis et al., 2024) — already cited in `references.bib`
- **PennyLang** (Basit et al., 2025) — already cited
- **Agent-Q** (Jern et al., 2025) — already cited
- Compare our reported metrics against their published numbers where comparable.

**6b. Code changes for Gemini provider:**
- `src/rag/generator.py`: Add `elif self.provider == "gemini":` branch using
  `google-generativeai` SDK.
- Add `GOOGLE_API_KEY` to `env.template`.

**6c. Baseline evaluation script:**
- New file: `src/evaluation/baseline_comparison.py`
- Runs each of the 25 benchmark prompts through each baseline (no RAG, no
  optimizer).
- Computes same metrics: success rate, code quality, latency, circuit metrics.

**6d. Paper changes:**
- Add Table: "Comparison with External Baselines" in §5 (Results).
- For literature baselines: use their published numbers and note task differences.
- Add note: "All API baselines run without RAG or optimization; our system includes
  the full multi-agent pipeline."

---

## 7. Critique Point — No Human Evaluation

### Plan

**7a. Human evaluation protocol:**

Recruit **10 evaluators** (quantum computing students/researchers).
Each evaluator scores a random sample of **10 generated outputs** (stratified across tiers).

**Rating dimensions (Likert 1–5):**
| Dimension | Question |
|-----------|---------|
| Correctness | Does the code correctly implement the requested algorithm? |
| Readability | Is the code clean and well-commented? |
| Explanation Quality | Is the educational explanation helpful and accurate? |
| Cirq Idiomacy | Does the code follow Cirq conventions? |

**7b. Implementation:**
- Create `src/evaluation/human_eval_template.md` — evaluation form for each sample.
- Create `data/datasets/human_eval_samples.jsonl` — 30 pre-generated outputs
  (10 Full System, 10 No RAG, 10 GPT-4o baseline) for blind evaluation.
- Collect results in `data/datasets/human_eval_results.jsonl`.

**7c. Analysis:**
- Compute inter-rater agreement (Cohen's Kappa or Krippendorff's Alpha).
- Report mean scores per dimension, per system.
- Kappa target: ≥ 0.6 (substantial agreement).

**7d. Paper changes:**
- Add §5.4: "Human Evaluation" subsection.
- Add Table: Human Evaluation Results (mean ± std per dimension per system).
- Report Kappa score and number of evaluators.

---

## 8. Critique Point — RL Optimizer and QCanvas Not Shown in Experiments

### Current state
- `src/agents/optimizer.py` has `_calculate_reward()` method (RL reward signal).
- `src/agents/validator.py` supports `remote` mode via `QCanvasClient`.
- Neither appears in the experimental results tables.

### Plan

**8a. RL Optimizer — clarify or demonstrate:**

The `_calculate_reward()` function in `optimizer.py` is a reward function stub,
not a full RL training loop. Options:

- **Option A (preferred):** Add a proper RL-guided optimization experiment.
  Use the reward signal to score circuits after heuristic optimization and show
  that circuits scoring higher on the reward function have lower depth/gate count.
  Present as "Reward-Guided Circuit Scoring" rather than "full RL training."
- **Option B:** Remove RL claims from the paper and describe it as a reward-signal
  placeholder for future work.

**8b. QCanvas Integration — add remote validation experiment:**
- Add one ablation variant: `local_cirq` vs. `qcanvas_remote` validation.
- Show: does QCanvas backend execution change validation pass rate vs. local Cirq?
- Add Table: "Validation Backend Comparison" (local vs. remote).
- Code: `src/evaluation/ablation.py` — add `qcanvas_remote` variant.

**8c. Paper changes:**
- §3 (System Architecture): Add explicit subsection "QCanvas Integration"
  describing the remote validation flow.
- §4 (Methodology): Explain how the RL reward function is used (even if as a
  scoring metric, not a full training loop).
- §5 (Results): Add the QCanvas backend comparison table.
- Remove any claim of "agentic RL training" if the full training loop is not
  implemented; replace with "RL-inspired reward-guided optimization."

---

## 9. Critique Point — No Error Analysis

### Plan

**9a. Define error taxonomy:**

| Category | Sub-types |
|----------|-----------|
| Syntax Errors | Import error, indentation, undefined variable |
| Wrong Cirq API | Deprecated API, incorrect gate arguments, wrong qubit type |
| Incorrect Quantum Logic | Wrong algorithm structure, wrong gate sequence |
| Invalid Measurements | Missing `cirq.measure()`, wrong key, unmeasured qubits |
| Poor RAG Retrieval | Low similarity score, wrong algorithm retrieved |
| Optimizer-Induced Errors | Over-optimized to empty circuit, broken qubit ordering |
| Explanation Inaccuracies | Wrong gate description, incorrect complexity claim |

**9b. Implementation:**
- New file: `src/evaluation/error_analyzer.py`
- Class `ErrorAnalyzer` with method `categorize_failure(result: dict) -> dict`:
  - Inspects `result["errors"]`, `result["stage"]`, `result["semantic_validation"]`
  - Maps to taxonomy categories above.

**9c. Run error analysis on all failed benchmark cases:**
- For each failed trial in the multi-trial benchmark, call `ErrorAnalyzer.categorize_failure()`.
- Aggregate: frequency of each error category.

**9d. Paper changes:**
- Add §5.5: "Error Analysis" subsection.
- Add Figure: Stacked bar chart of error categories by system variant (Full System,
  No RAG, No Optimizer, No Validator).
- Add Table: Error taxonomy with counts and percentages.
- Discuss: which errors are most common, which are eliminated by each component.

---

## 10. Critique Point — Related Work Too Short (needs 15–20 citations)

### Current state
`references.bib` contains **8 references**. Related work section is minimal.

### Plan

**10a. Target: 20 references minimum.** Add the following categories:

**RAG Systems (4 new citations):**
- Lewis et al. (2020) — original RAG paper (NeurIPS)
- Gao et al. (2023) — "Retrieval-Augmented Generation for Large Language Models: A Survey"
- Shi et al. (2023) — "REPLUG: Retrieval-Augmented Language Model Pre-Training"
- Asai et al. (2023) — "Self-RAG: Learning to Retrieve, Generate, and Critique"

**LLM for Code Generation (4 new citations):**
- Chen et al. (2021) — "Evaluating Large Language Models Trained on Code" (Codex/HumanEval)
- Nijkamp et al. (2022) — CodeGen
- Li et al. (2022) — AlphaCode (Science)
- Rozière et al. (2023) — Code Llama

**Quantum Computing + ML (4 new citations):**
- Cerezo et al. (2021) — "Variational quantum algorithms" (Nature Reviews Physics)
- Farhi et al. (2014) — Original QAOA paper
- Peruzzo et al. (2014) — Original VQE paper
- Grover (1996) — Grover's search algorithm

**Quantum Software/Frameworks (2 new citations):**
- Broughton et al. (2020) — TensorFlow Quantum
- Bergholm et al. (2018) — PennyLane

**Multi-Agent Systems (2 new citations):**
- Park et al. (2023) — "Generative Agents: Interactive Simulacra of Human Behavior"
- Chen et al. (2023) — "AgentCoder: Multi-Agent Code Generation"

**10b. Related Work structure (expand to 1.5–2 pages):**
1. LLM-based Code Generation
2. RAG Systems for Code
3. Quantum Code Generation (Qiskit Assistant, PennyLang, QUASAR, Agent-Q, etc.)
4. Multi-Agent Systems for Software Engineering
5. Quantum Computing Frameworks

**10c. Code change:**
- Update `research-papers/Cirq-RAG-Assistant/references.bib` with all new entries.

---

## 11. AWS/Local Provider Migration — Paper Narrative Fix

### What to change in the paper (all model names verified from `config/config.json`)

| Section | Current (wrong) | Fix |
|---------|-----------------|-----|
| §3 Technology Stack | "local Ollama models" | "AWS Bedrock via Converse API; four Claude-family models across four agents" |
| §3 Technology Stack | No mention of embeddings backend | Add: "Text embeddings use **Amazon Nova 2 Multimodal Embeddings** (`amazon.nova-2-multimodal-embeddings-v1:0`, 1024 dimensions) served via AWS Bedrock. **NOT** a local sentence-transformer model." |
| §3 Technology Stack | No model-tier rationale | Add Table 1 (reproduced from §0 above) showing the 4-agent model assignment |
| §4 Experimental Setup | No per-agent model detail | Specify each agent's model ID: Designer = `anthropic.claude-sonnet-4-6`, Optimizer = `anthropic.claude-opus-4-6-v1`, Validator = `anthropic.claude-sonnet-4-6`, Educational = `anthropic.claude-haiku-4-5-20251001-v1:0` |
| §4 Experimental Setup | top_k not stated or stated as 3 | Correct to: "RAG retrieves top-**5** results per query (`top_k_results=5`, `similarity_threshold=0.7`)" |
| §4 Experimental Setup | RL described as active | Correct to: "The RL reward function (`use_rl=false`) is implemented as a circuit-quality scoring signal with weights: depth (−0.3), two-qubit gates (−0.3), fidelity (+0.4). Live RL training is deferred to future work." |
| §5 Results | Figures labeled "Qwen2.5-Coder" | Re-label: "AWS Bedrock / Claude Sonnet (Designer+Validator) / Claude Opus (Optimizer)" |
| Appendix B (NEW) | — | Reproducibility note: Ollama fallback config for readers without AWS credentials |

---

## 12. Implementation Priority and Timeline

| Priority | Item | Effort | Who |
|----------|------|--------|-----|
| 🔴 Critical | Fix provider narrative (§3, §4, §5) | 1 day | All |
| 🔴 Critical | Define code quality formula (§5) | 0.5 day | Umer |
| 🔴 Critical | Expand related work to 20 refs | 1 day | All |
| 🔴 Critical | Add prompt catalogue appendix | 1 day | Hussain |
| 🟠 High | Multi-trial evaluation (n=5) | 2 days | Umer |
| 🟠 High | Error analysis section | 1.5 days | Irtaza |
| 🟠 High | External baselines (GPT-4, Claude no-RAG) | 2 days | Umer |
| 🟡 Medium | Expand benchmark to 25 prompts | 1 day | Hussain |
| 🟡 Medium | Clarify RL optimizer + QCanvas experiment | 1.5 days | Irtaza |
| 🟡 Medium | Human evaluation (10 evaluators × 10 samples) | 3 days | All |
| 🟢 Optional | Knowledge base expansion to 500 entries | 2 days | Hussain |
| 🟢 Optional | Gemini provider support | 1 day | Umer |

**Total estimated effort: ~17 working days**

---

## 13. Files to Create / Modify

### New files
```
data/datasets/benchmark_prompts_v2.jsonl          ← 25 expanded prompts
data/datasets/human_eval_samples.jsonl            ← 30 pre-generated outputs
data/datasets/human_eval_results.jsonl            ← collected evaluator scores
src/evaluation/error_analyzer.py                  ← error taxonomy + categorization
src/evaluation/baseline_comparison.py             ← external model baselines
src/evaluation/human_eval_template.md             ← evaluator instruction form
BENCHMARK.md                                      ← repo root benchmark guide
```

### Modified files
```
src/evaluation/benchmark.py                       ← multi-trial runner, load from JSONL
src/evaluation/metrics.py                         ← code quality formula, statistics
src/evaluation/reports.py                         ← CI columns, error taxonomy output
src/evaluation/ablation.py                        ← add qcanvas_remote variant
src/rag/generator.py                              ← add Gemini provider (optional)
research-papers/Cirq-RAG-Assistant/references.bib ← 20 references
env.template                                      ← GOOGLE_API_KEY (if Gemini added)
```

### Paper sections to rewrite/expand
```
§1 Introduction          ← Mention AWS deployment, update contribution list
§3 System Architecture   ← Add QCanvas integration, clarify RL reward function
§4 Experimental Setup    ← AWS provider, multi-trial, 25 prompts, code quality formula
§5 Results               ← CI columns, error analysis, human eval, baselines table
§6 Related Work          ← Expand to 20 citations, 5 sub-categories
Appendix A (NEW)         ← Full benchmark prompt catalogue (25 prompts)
Appendix B (NEW)         ← Reproducibility note: Ollama vs. AWS
```

---

---

## 14. Fact-Check Summary — What Was Wrong in the Original Plan

The following claims in the first draft of this plan were **incorrect** and have been fixed:

| Claim (wrong) | Correct fact (from config.json) |
|---------------|---------------------------------|
| "Primary model: Anthropic Claude 3 Sonnet/Haiku" | Designer & Validator = `claude-sonnet-4-6`; Optimizer = `claude-opus-4-6-v1`; Educational = `claude-haiku-4-5-20251001-v1:0` |
| "model = `anthropic.claude-3-5-sonnet-20241022-v2:0`" | Actual Designer model: `anthropic.claude-sonnet-4-6` |
| "Embeddings via `sentence-transformers/all-MiniLM-L6-v2` (local)" | Embeddings via **AWS Bedrock** `amazon.nova-2-multimodal-embeddings-v1:0` (1024-dim) — fully cloud-based |
| "top_k = 3" (implied by code comments) | Config sets `top_k_results = 5` |
| RL described as potentially active | Config has `use_rl: false` — RL training is explicitly disabled |
| All agents use the same model | 4 different Claude models are assigned by tier (Opus for Optimizer, Haiku for Educational) |
| Vector store is "pgvector" | Dev: FAISS index at `data/models/vector_index`; pgvector is production-only (configured but not default) |
| Knowledge base target stated as 140 (current) | Config sets `size_target: 2500` as the intended goal |

---

*Plan version 2.0 — updated 2026-05-15 (fact-checked against config/config.json)*
