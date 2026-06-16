"""
run_local_benchmark.py
======================
Two-phase benchmark runner:
  Phase 1 - Curated KB  (140 entries, backed-up originals)
  Phase 2 - Expanded KB (700 entries, current files)

Each phase:
  1. Rebuilds the FAISS vector index from the active KB files
  2. Runs all 25 benchmark prompts through the RAG pipeline
  3. Scores each result with the code quality formula from the revision plan
  4. Saves a JSON report and prints a summary table

Usage:
  python scripts/run_local_benchmark.py                      # both phases
  python scripts/run_local_benchmark.py --phase 1            # curated only
  python scripts/run_local_benchmark.py --phase 2            # expanded only
  python scripts/run_local_benchmark.py --prompts 5          # first N prompts (fast test)

Requirements:
  - Ollama running with qwen2.5-coder:7b-instruct-q4_K_M pulled
  - sentence-transformers installed  (pip install sentence-transformers)
  - faiss-cpu installed              (pip install faiss-cpu)
  - cirq installed                   (pip install cirq)
"""

import ast
import json
import os
import sys

# ── Force CPU-only embedding mode ────────────────────────────────────────────
# RTX 5060 (sm_120) is incompatible with PyTorch 2.5.1 (max sm_90).
# The EmbeddingModel._determine_device() has a dotted-path config lookup bug
# that always returns "cuda" when a GPU is physically present. We force CPU
# by explicitly constructing EmbeddingModel(device="cpu") in build_index().
# CUDA_VISIBLE_DEVICES is set here as a belt-and-braces safety measure but
# may not take effect after torch is already imported by config_loader.
os.environ["CUDA_VISIBLE_DEVICES"] = "-1"

import time
import shutil
import argparse
import traceback
from datetime import datetime
from pathlib import Path

# ── Resolve project root so imports work from anywhere ───────────────────────
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
# config_loader auto-picks config/config.dev.json when ENVIRONMENT=development (default)

# ── Paths ────────────────────────────────────────────────────────────────────
KB_DIR        = PROJECT_ROOT / "data" / "knowledge_base"
VECTOR_INDEX  = PROJECT_ROOT / "data" / "models" / "vector_index"
PROMPTS_FILE  = PROJECT_ROOT / "data" / "datasets" / "benchmark_prompts_v2.jsonl"
REPORTS_DIR   = PROJECT_ROOT / "outputs" / "reports"
import glob

def get_latest_backup(prefix: str) -> Path:
    pattern = str(KB_DIR / f"{prefix}.backup_*.jsonl")
    matches = glob.glob(pattern)
    if not matches:
        return KB_DIR / f"{prefix}.backup_NOT_FOUND.jsonl" # fallback
    matches.sort(reverse=True)
    return Path(matches[0])

KB_FILES = {
    "designer":  KB_DIR / "curated_designer_examples.jsonl",
    "optimizer": KB_DIR / "curated_optimizer_examples.jsonl",
    "validator": KB_DIR / "curated_validator_examples.jsonl",
}
BACKUP_FILES = {
    "designer":  get_latest_backup("curated_designer_examples"),
    "optimizer": get_latest_backup("curated_optimizer_examples"),
    "validator": get_latest_backup("curated_validator_examples"),
}

TIER_ORDER = ["basic", "intermediate", "algorithm", "advanced", "explanation"]


# =============================================================================
#  Code Quality Scoring
# =============================================================================

def score_code_quality(code: str, validation_result: dict) -> dict:
    """
    CodeQuality(c) = 0.30 * SyntaxValid
                   + 0.30 * CompilationSuccess
                   + 0.20 * HasMeasurement
                   + 0.10 * CircuitNonEmpty
                   + 0.10 * CorrectImports
    """
    if not code or not code.strip():
        return {"score": 0.0, "syntax_valid": False, "compilation_success": False,
                "has_measurement": False, "circuit_non_empty": False, "correct_imports": False}

    try:
        ast.parse(code)
        syntax_valid = True
    except SyntaxError:
        syntax_valid = False

    compilation_success = bool(
        validation_result.get("compilation", {}).get("success", False)
        or validation_result.get("validation_passed", False)
    )
    has_measurement = ("cirq.measure" in code or "measure_each" in code
                       or "MeasurementGate" in code)
    circuit_non_empty = ("cirq.Circuit" in code or "circuit.append" in code
                         or "Circuit(" in code)
    correct_imports = "import cirq" in code or "from cirq" in code

    score = (0.30 * syntax_valid + 0.30 * compilation_success
             + 0.20 * has_measurement + 0.10 * circuit_non_empty
             + 0.10 * correct_imports)

    return {
        "score": round(score, 4),
        "syntax_valid": syntax_valid,
        "compilation_success": compilation_success,
        "has_measurement": has_measurement,
        "circuit_non_empty": circuit_non_empty,
        "correct_imports": correct_imports,
    }


# =============================================================================
#  KB switching helpers
# =============================================================================

def count_kb_lines():
    total = 0
    for f in KB_FILES.values():
        if f.exists():
            with open(f) as fh:
                total += sum(1 for line in fh if line.strip())
    return total


def switch_to_curated():
    """Replace current KB files with their backed-up curated versions (140 entries)."""
    print("  Switching to CURATED KB (140 entries)...")
    all_present = all(b.exists() for b in BACKUP_FILES.values())
    if not all_present:
        missing = [str(b) for b in BACKUP_FILES.values() if not b.exists()]
        print("  [WARN] Backup files not found:\n    " + "\n    ".join(missing))
        print("  Using whatever is currently in the KB directory.")
        return False
    for key in KB_FILES:
        shutil.copy2(BACKUP_FILES[key], KB_FILES[key])
        print("    Restored {}  <-  {}".format(KB_FILES[key].name, BACKUP_FILES[key].name))
    n = count_kb_lines()
    print("  KB entries active: {}".format(n))
    return True


def nuke_vector_index():
    """Delete the FAISS index so it gets rebuilt from the current KB."""
    if VECTOR_INDEX.exists():
        shutil.rmtree(VECTOR_INDEX, ignore_errors=True)
        print("  Deleted old FAISS index at {}".format(VECTOR_INDEX))
    else:
        print("  No existing FAISS index (will be built fresh)")


# =============================================================================
#  FAISS index build
# =============================================================================

def build_index():
    """Build the FAISS vector index from the current KB files using CPU embeddings."""
    print("  Building FAISS index from current KB...")
    t0 = time.time()
    try:
        from src.rag.embeddings import EmbeddingModel
        from src.rag.knowledge_base import KnowledgeBase

        # Explicitly pass device="cpu" to bypass the broken auto-detection in
        # EmbeddingModel._determine_device() which always picks "cuda" via a
        # dotted-path config lookup bug (plain dict doesn't support dotted keys).
        emb_model = EmbeddingModel(device="cpu")
        kb = KnowledgeBase(embedding_model=emb_model)

        # Load all active JSONL files (skip backup files)
        n_loaded = 0
        for jf in sorted(kb.knowledge_base_path.glob("*.jsonl")):
            if "backup" in jf.name:
                continue
            try:
                n_loaded += kb.load_from_jsonl(jf)
            except Exception as e:
                print("    [WARN] Could not load {}: {}".format(jf.name, e))

        print("    Loaded {} documents from KB".format(n_loaded))
        if not kb.entries:
            print("  [ERROR] Knowledge base is empty!")
            return False

        print("    Encoding and indexing {} documents on CPU...".format(len(kb.entries)))
        kb.index_entries(batch_size=64)
        kb.save_index()

        elapsed = time.time() - t0
        print("    Index built in {:.1f}s  ({} entries)".format(elapsed, len(kb.entries)))
        return True

    except Exception as e:
        print("  [ERROR] Failed to build index: {}".format(e))
        traceback.print_exc()
        return False


# =============================================================================
#  Single benchmark prompt runner
# =============================================================================

def run_single_prompt(prompt: dict, orchestrator) -> dict:
    """Run one benchmark prompt and return a scored result dict."""
    t0 = time.time()
    query = prompt["query"]
    algorithm = prompt.get("algorithm")

    try:
        result = orchestrator.generate_code(
            query=query,
            algorithm=algorithm,
            optimize=True,
            validate=True,
            explain=False,
        )
        latency = time.time() - t0

        code = result.get("code") or ""
        validation = result.get("validation") or {}
        quality = score_code_quality(code, validation)
        passed = result.get("success", False) and validation.get("validation_passed", False)

        return {
            "id": prompt["id"],
            "tier": prompt["tier"],
            "query": query,
            "algorithm": algorithm,
            "success": result.get("success", False),
            "validation_passed": validation.get("validation_passed", False),
            "passed": passed,
            "latency_s": round(latency, 2),
            "code_quality": quality,
            "code_length": len(code),
            "code_lines": len(code.split("\n")) if code else 0,
            "context_used": result.get("context_used", 0),
            "errors": result.get("errors") or [],
        }

    except Exception as e:
        latency = time.time() - t0
        return {
            "id": prompt["id"],
            "tier": prompt["tier"],
            "query": query,
            "algorithm": algorithm,
            "success": False,
            "validation_passed": False,
            "passed": False,
            "latency_s": round(latency, 2),
            "code_quality": {"score": 0.0},
            "code_length": 0,
            "code_lines": 0,
            "context_used": 0,
            "errors": [str(e)],
            "exception": traceback.format_exc(),
        }


# =============================================================================
#  Phase runner
# =============================================================================

def run_phase(phase_name: str, kb_size: int, prompts: list, max_prompts: int) -> dict:
    """Run a full benchmark phase and return the results dict."""
    print("\n" + "=" * 60)
    print("  PHASE: {}".format(phase_name))
    print("  KB size: {} entries  |  Prompts: {}".format(kb_size, min(len(prompts), max_prompts)))
    print("=" * 60)

    if not build_index():
        print("  [ABORT] Cannot proceed without a valid index.")
        return {}

    print("\n  Initializing orchestrator...")
    try:
        from src.orchestration.orchestrator import Orchestrator
        from src.agents.designer import DesignerAgent
        from src.agents.validator import ValidatorAgent
        from src.agents.optimizer import OptimizerAgent
        from src.rag.retriever import Retriever
        from src.rag.generator import Generator
        from src.rag.knowledge_base import KnowledgeBase
        from src.rag.embeddings import EmbeddingModel
        
        # We need the KnowledgeBase loaded to instantiate the Retriever
        emb_model = EmbeddingModel(device="cpu")
        kb = KnowledgeBase(embedding_model=emb_model)
        for jf in sorted(kb.knowledge_base_path.glob("*.jsonl")):
            if "backup" not in jf.name:
                kb.load_from_jsonl(jf)
                
        retriever = Retriever(knowledge_base=kb)
        generator = Generator(retriever=retriever)
        designer = DesignerAgent(retriever=retriever, generator=generator)
        validator = ValidatorAgent(retriever=retriever)
        optimizer = OptimizerAgent(retriever=retriever)
        
        orchestrator = Orchestrator(
            designer=designer,
            validator=validator,
            optimizer=optimizer
        )
        print("  Orchestrator ready.")
    except Exception as e:
        print("  [ERROR] Failed to init orchestrator: {}".format(e))
        traceback.print_exc()
        return {}

    active_prompts = prompts[:max_prompts]
    results = []
    passed_total = 0

    for i, prompt in enumerate(active_prompts, 1):
        print("\n  [{:02d}/{}] {} - {}...".format(
            i, len(active_prompts), prompt["tier"].upper(), prompt["query"][:60]))
        r = run_single_prompt(prompt, orchestrator)
        results.append(r)

        status = "[PASS]" if r["passed"] else "[FAIL]"
        qs = r["code_quality"].get("score", 0.0)
        print("         {}  quality={:.2f}  latency={}s  ctx={}".format(
            status, qs, r["latency_s"], r["context_used"]))

        if r["passed"]:
            passed_total += 1
        if r.get("errors"):
            print("         [!] {}".format(str(r["errors"][0])[:120]))

    n = len(results)
    pass_rate = passed_total / n if n > 0 else 0
    avg_quality = sum(r["code_quality"].get("score", 0) for r in results) / n if n > 0 else 0
    avg_latency = sum(r["latency_s"] for r in results) / n if n > 0 else 0

    tier_stats = {}
    for tier in TIER_ORDER:
        tr = [r for r in results if r["tier"] == tier]
        if tr:
            tier_stats[tier] = {
                "count": len(tr),
                "passed": sum(1 for r in tr if r["passed"]),
                "pass_rate": sum(1 for r in tr if r["passed"]) / len(tr),
                "avg_quality": sum(r["code_quality"].get("score", 0) for r in tr) / len(tr),
            }

    return {
        "phase": phase_name,
        "kb_size": kb_size,
        "timestamp": datetime.now().isoformat(),
        "total_prompts": n,
        "passed": passed_total,
        "failed": n - passed_total,
        "pass_rate": round(pass_rate, 4),
        "avg_quality_score": round(avg_quality, 4),
        "avg_latency_s": round(avg_latency, 2),
        "tier_breakdown": tier_stats,
        "prompt_results": results,
    }


# =============================================================================
#  Report and comparison
# =============================================================================

def print_phase_summary(phase_data: dict):
    print("\n  --- {} Summary ---".format(phase_data["phase"]))
    print("  Pass rate    : {:.1f}%  ({}/{})".format(
        phase_data["pass_rate"] * 100, phase_data["passed"], phase_data["total_prompts"]))
    print("  Avg quality  : {:.4f}".format(phase_data["avg_quality_score"]))
    print("  Avg latency  : {}s".format(phase_data["avg_latency_s"]))
    if phase_data.get("tier_breakdown"):
        print("\n  {:<16} {:>4} {:>5} {:>7} {:>9}".format("Tier", "N", "Pass", "Pass%", "Quality"))
        print("  " + "-" * 46)
        for tier in TIER_ORDER:
            ts = phase_data["tier_breakdown"].get(tier)
            if ts:
                print("  {:<16} {:>4} {:>5} {:>6.1f}% {:>9.4f}".format(
                    tier, ts["count"], ts["passed"],
                    ts["pass_rate"] * 100, ts["avg_quality"]))


def print_comparison(p1: dict, p2: dict):
    print("\n" + "=" * 60)
    print("  COMPARISON: {}  vs  {}".format(p1["phase"], p2["phase"]))
    print("=" * 60)

    def delta(a, b, pct=False):
        d = b - a
        sign = "+" if d >= 0 else ""
        return "{}{:.1f}pp".format(sign, d * 100) if pct else "{}{:.4f}".format(sign, d)

    print("\n  {:<22} {:>10} {:>10} {:>10}".format("Metric", "Curated", "Expanded", "Delta"))
    print("  " + "-" * 54)
    print("  {:<22} {:>9.1f}% {:>9.1f}% {:>10}".format(
        "Pass rate", p1["pass_rate"] * 100, p2["pass_rate"] * 100,
        delta(p1["pass_rate"], p2["pass_rate"], pct=True)))
    print("  {:<22} {:>10.4f} {:>10.4f} {:>10}".format(
        "Avg quality score", p1["avg_quality_score"], p2["avg_quality_score"],
        delta(p1["avg_quality_score"], p2["avg_quality_score"])))
    d_lat = p2["avg_latency_s"] - p1["avg_latency_s"]
    print("  {:<22} {:>10.2f} {:>10.2f} {:>+10.2f}s".format(
        "Avg latency (s)", p1["avg_latency_s"], p2["avg_latency_s"], d_lat))

    print("\n  Per-tier pass rate comparison:")
    print("  {:<16} {:>10} {:>11} {:>8}".format("Tier", "Curated%", "Expanded%", "Delta"))
    print("  " + "-" * 48)
    for tier in TIER_ORDER:
        t1 = p1.get("tier_breakdown", {}).get(tier)
        t2 = p2.get("tier_breakdown", {}).get(tier)
        if t1 and t2:
            d = (t2["pass_rate"] - t1["pass_rate"]) * 100
            print("  {:<16} {:>9.1f}% {:>10.1f}% {:>+8.1f}pp".format(
                tier, t1["pass_rate"] * 100, t2["pass_rate"] * 100, d))

    if p2["pass_rate"] > p1["pass_rate"]:
        verdict = "EXPANDED KB is better"
    elif p1["pass_rate"] > p2["pass_rate"]:
        verdict = "CURATED KB is better"
    else:
        verdict = "No significant difference in pass rate"
    print("\n  Verdict: {}".format(verdict))


def save_report(all_phases: list, output_path: Path):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"benchmark_run": datetime.now().isoformat(), "phases": all_phases}, f, indent=2)
    print("\n  Report saved: {}".format(output_path))


# =============================================================================
#  Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser(description="Two-phase Cirq RAG benchmark runner")
    parser.add_argument("--phase", type=int, choices=[1, 2], default=0,
                        help="Run only phase 1 (curated) or 2 (expanded). Default: both.")
    parser.add_argument("--prompts", type=int, default=25,
                        help="Number of prompts to run (default: 25)")
    args = parser.parse_args()

    if not PROMPTS_FILE.exists():
        print("[ERROR] Benchmark prompts file not found: {}".format(PROMPTS_FILE))
        sys.exit(1)

    prompts = []
    with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                prompts.append(json.loads(line))
    print("Loaded {} benchmark prompts from {}".format(len(prompts), PROMPTS_FILE.name))

    all_results = []
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = REPORTS_DIR / "benchmark_comparison_{}.json".format(ts)

    run_phase1 = args.phase in (0, 1)
    run_phase2 = args.phase in (0, 2)
    phase1_result = {}
    phase2_result = {}

    # Save expanded KB before overwriting it for Phase 1
    EXPANDED_BACKUP_DIR = PROJECT_ROOT / ".cache" / "expanded_kb_temp"
    if run_phase1 and run_phase2:
        EXPANDED_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        for key, src in KB_FILES.items():
            if src.exists():
                shutil.copy2(src, EXPANDED_BACKUP_DIR / src.name)
        print("\nExpanded KB saved temporarily to {}".format(EXPANDED_BACKUP_DIR))

    # -- PHASE 1: Curated KB --------------------------------------------------
    if run_phase1:
        switch_to_curated()
        nuke_vector_index()
        kb_size = count_kb_lines()
        phase1_result = run_phase(
            phase_name="Phase 1 - Curated KB (140 entries)",
            kb_size=kb_size,
            prompts=prompts,
            max_prompts=args.prompts,
        )
        if phase1_result:
            all_results.append(phase1_result)
            print_phase_summary(phase1_result)

    # -- PHASE 2: Expanded KB -------------------------------------------------
    if run_phase2:
        if run_phase1 and EXPANDED_BACKUP_DIR.exists():
            print("\n  Restoring EXPANDED KB...")
            for key, dst in KB_FILES.items():
                src = EXPANDED_BACKUP_DIR / dst.name
                if src.exists():
                    shutil.copy2(src, dst)
                    print("    Restored {}".format(dst.name))
        nuke_vector_index()
        kb_size = count_kb_lines()
        phase2_result = run_phase(
            phase_name="Phase 2 - Expanded KB (700 entries)",
            kb_size=kb_size,
            prompts=prompts,
            max_prompts=args.prompts,
        )
        if phase2_result:
            all_results.append(phase2_result)
            print_phase_summary(phase2_result)

    # Cleanup
    if EXPANDED_BACKUP_DIR.exists():
        shutil.rmtree(EXPANDED_BACKUP_DIR, ignore_errors=True)

    if phase1_result and phase2_result:
        print_comparison(phase1_result, phase2_result)

    if all_results:
        save_report(all_results, report_path)
        
    print("\n  [Cleanup] Restoring Curated KB as default system configuration...")
    switch_to_curated()
    nuke_vector_index()

    print("\nDone.")


if __name__ == "__main__":
    main()
