"""
expand_knowledge_base.py
========================
Expands the Cirq RAG knowledge base from two source datasets:
  - data/datasets/annotated_cirq_dataset.jsonl   (has description field)
  - data/datasets/processed_cirq_dataset.jsonl   (description may be empty)

Filtering strategy (no quality_score field):
  - code length >= 200 chars
  - description length >= 40 chars  (annotated dataset only)
  - contains 'import cirq' or 'cirq.Circuit' in code
  - excludes test files (_test.py)

Tagging strategy:
  - designer:   default bucket (circuit construction, algorithms)
  - optimizer:  code mentions optimiz / transpil / compile / depth / gate_count / simplif
  - validator:  code mentions validate / validate_circuit / assert / pytest / verify

Targets:
  - designer:   fill up to 500 (currently 107, need ~393 more)
  - optimizer:  fill up to 100 (currently 18,  need ~82  more)
  - validator:  fill up to 100 (currently 15,  need ~85  more)

Output: appends to existing knowledge_base/*.jsonl files (preserving current entries).
Creates backup copies before writing.
"""

import json
import re
import os
import shutil
import hashlib
from pathlib import Path
from datetime import datetime

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent  # Cirq-RAG-Code-Assistant/
DATA_DIR = BASE_DIR / "data"
KB_DIR   = DATA_DIR / "knowledge_base"
DS_DIR   = DATA_DIR / "datasets"

ANNOTATED_DATASET = DS_DIR / "annotated_cirq_dataset.jsonl"
PROCESSED_DATASET = DS_DIR / "processed_cirq_dataset.jsonl"

DESIGNER_KB  = KB_DIR / "curated_designer_examples.jsonl"
OPTIMIZER_KB = KB_DIR / "curated_optimizer_examples.jsonl"
VALIDATOR_KB = KB_DIR / "curated_validator_examples.jsonl"

# ── Targets ──────────────────────────────────────────────────────────────────
TARGET_DESIGNER  = 500
TARGET_OPTIMIZER = 100
TARGET_VALIDATOR = 100

# ── Quality thresholds ───────────────────────────────────────────────────────
MIN_CODE_LEN        = 200
MIN_DESC_LEN        = 40   # only required for annotated dataset entries
MIN_CODE_LINES      = 8    # at least 8 non-empty lines of code

# ── Tagging keyword sets ─────────────────────────────────────────────────────
OPTIMIZER_KEYWORDS = re.compile(
    r'\b(optim|transpil|compil|simplif|gate_count|circuit_depth|moment|'
    r'two_qubit_gate|single_qubit_gate|depth|reduce|minimize|decompos)\b',
    re.IGNORECASE
)
VALIDATOR_KEYWORDS = re.compile(
    r'\b(validate|assert|pytest|verify|check|test_|unittest|valid_circuit|'
    r'validate_operation|validate_circuit|raises|expect)\b',
    re.IGNORECASE
)


def compute_hash(code: str) -> str:
    return hashlib.md5(code.encode()).hexdigest()


def passes_quality_filter(entry: dict, require_description: bool = True) -> bool:
    code = entry.get("code", "")
    description = entry.get("description", "")
    filename = entry.get("file", "")

    # Exclude test files
    if "_test.py" in filename or "test_" in filename:
        return False

    # Must contain cirq
    if "import cirq" not in code and "cirq.Circuit" not in code and "cirq." not in code:
        return False

    # Code length
    if len(code) < MIN_CODE_LEN:
        return False

    # Non-empty lines of code
    non_empty_lines = [l for l in code.split("\n") if l.strip()]
    if len(non_empty_lines) < MIN_CODE_LINES:
        return False

    # Description required for annotated dataset
    if require_description and len(description.strip()) < MIN_DESC_LEN:
        return False

    return True


def tag_entry(code: str) -> str:
    """Returns 'validator', 'optimizer', or 'designer'."""
    if VALIDATOR_KEYWORDS.search(code):
        return "validator"
    if OPTIMIZER_KEYWORDS.search(code):
        return "optimizer"
    return "designer"


def load_existing_hashes(kb_file: Path) -> set:
    """Load existing knowledge base entries and return set of code hashes."""
    hashes = set()
    if not kb_file.exists():
        return hashes
    with open(kb_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                hashes.add(compute_hash(entry.get("code", "")))
            except json.JSONDecodeError:
                pass
    return hashes


def count_existing(kb_file: Path) -> int:
    if not kb_file.exists():
        return 0
    with open(kb_file, "r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def backup_file(kb_file: Path):
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = kb_file.with_suffix(f".backup_{ts}.jsonl")
    shutil.copy2(kb_file, backup)
    print(f"  [backup] {backup.name}")


def build_new_entry_from_annotated(raw: dict, idx: int, bucket: str) -> dict:
    """Convert annotated dataset format → KB designer format."""
    code = raw.get("code", "")
    description = raw.get("description", "")
    filename = raw.get("file", "unknown")

    # Derive topics from description keywords
    topics = []
    desc_lower = description.lower()
    topic_map = {
        "bell": "bell_state", "grover": "grover", "vqe": "vqe", "qaoa": "qaoa",
        "qft": "qft", "teleport": "teleportation", "noise": "noise_model",
        "entangl": "entanglement", "hadamard": "hadamard", "cnot": "cnot",
        "measurement": "measurement", "superposition": "superposition",
        "ghz": "ghz_state", "fourier": "qft", "amplitude": "amplitude_estimation",
        "phase": "phase_estimation", "depolariz": "depolarizing_noise",
        "simulator": "simulation", "parametric": "parametric_circuit",
        "variational": "variational", "circuit": "circuit_construction",
        "swap": "swap", "toffoli": "toffoli", "optimize": "optimization",
        "validate": "validation", "compile": "compilation",
    }
    for keyword, topic in topic_map.items():
        if keyword in desc_lower and topic not in topics:
            topics.append(topic)
    if not topics:
        topics = ["cirq_code"]

    # Difficulty heuristic
    code_lines = len([l for l in code.split("\n") if l.strip()])
    if code_lines < 20:
        difficulty = "beginner"
    elif code_lines < 60:
        difficulty = "intermediate"
    else:
        difficulty = "advanced"

    entry_id = f"expanded_{bucket}_{idx:04d}"
    task = description[:200] if description else f"Cirq code example from {filename}"

    return {
        "id": entry_id,
        "difficulty": difficulty,
        "topics": topics,
        "task": task,
        "constraints": [
            f"Source file: {filename}",
            "Uses Cirq quantum computing framework",
        ],
        "code": code,
        "source": "annotated_cirq_dataset",
    }


def build_new_entry_from_processed(raw: dict, idx: int, bucket: str) -> dict:
    """Convert processed dataset format → KB designer format."""
    code = raw.get("code", "")
    filename = raw.get("file", "unknown")

    # Extract topics from code content
    topics = []
    code_lower = code.lower()
    topic_map = {
        "grover": "grover", "bell": "bell_state", "vqe": "vqe", "qaoa": "qaoa",
        "qft": "qft", "teleport": "teleportation", "ghz": "ghz_state",
        "depolarize": "depolarizing_noise", "simulator": "simulation",
        "lineQubit": "line_qubit", "GridQubit": "grid_qubit",
        "NamedQubit": "named_qubit", "cirq.Circuit": "circuit_construction",
        "cirq.moment": "moments", "cirq.H": "hadamard", "cirq.CNOT": "cnot",
        "cirq.measure": "measurement", "cirq.Simulator": "simulation",
    }
    for keyword, topic in topic_map.items():
        if keyword.lower() in code_lower and topic not in topics:
            topics.append(topic)
    if not topics:
        topics = ["cirq_code"]

    code_lines = len([l for l in code.split("\n") if l.strip()])
    if code_lines < 20:
        difficulty = "beginner"
    elif code_lines < 60:
        difficulty = "intermediate"
    else:
        difficulty = "advanced"

    entry_id = f"expanded_{bucket}_proc_{idx:04d}"
    # Generate a task description from the filename
    task_name = filename.replace(".py", "").replace("_", " ").replace("-", " ").title()
    task = f"Implement {task_name} using the Cirq quantum computing framework."

    return {
        "id": entry_id,
        "difficulty": difficulty,
        "topics": topics,
        "task": task,
        "constraints": [
            f"Source file: {filename}",
            "Uses Cirq quantum computing framework",
        ],
        "code": code,
        "source": "processed_cirq_dataset",
    }


def load_source_dataset(filepath: Path, require_description: bool) -> list[dict]:
    """Load, filter, and tag entries from a source dataset file."""
    entries = []
    print(f"\n  Loading {filepath.name}...")
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                raw = json.loads(line)
                if passes_quality_filter(raw, require_description=require_description):
                    bucket = tag_entry(raw.get("code", ""))
                    entries.append((raw, bucket))
            except json.JSONDecodeError:
                continue
    print(f"  -> {len(entries)} entries passed quality filter")
    return entries


def expand_knowledge_base():
    print("=" * 60)
    print("  Cirq RAG Knowledge Base Expansion Script")
    print("=" * 60)

    # ── Count current entries ─────────────────────────────────────────────
    cur_designer  = count_existing(DESIGNER_KB)
    cur_optimizer = count_existing(OPTIMIZER_KB)
    cur_validator = count_existing(VALIDATOR_KB)
    print(f"\nCurrent KB entries:")
    print(f"  Designer:  {cur_designer}")
    print(f"  Optimizer: {cur_optimizer}")
    print(f"  Validator: {cur_validator}")
    print(f"\nTargets:")
    print(f"  Designer:  {TARGET_DESIGNER}  (need {max(0, TARGET_DESIGNER  - cur_designer)}  more)")
    print(f"  Optimizer: {TARGET_OPTIMIZER} (need {max(0, TARGET_OPTIMIZER - cur_optimizer)} more)")
    print(f"  Validator: {TARGET_VALIDATOR} (need {max(0, TARGET_VALIDATOR - cur_validator)} more)")

    need_designer  = max(0, TARGET_DESIGNER  - cur_designer)
    need_optimizer = max(0, TARGET_OPTIMIZER - cur_optimizer)
    need_validator = max(0, TARGET_VALIDATOR - cur_validator)

    if need_designer == 0 and need_optimizer == 0 and need_validator == 0:
        print("\nAll targets already met. Nothing to do.")
        return

    # ── Load existing hashes to avoid duplicates ──────────────────────────
    print("\nLoading existing hashes for deduplication...")
    existing_hashes = (
        load_existing_hashes(DESIGNER_KB)
        | load_existing_hashes(OPTIMIZER_KB)
        | load_existing_hashes(VALIDATOR_KB)
    )
    print(f"  {len(existing_hashes)} unique existing code hashes loaded")

    # ── Load source data ──────────────────────────────────────────────────
    annotated_entries = load_source_dataset(ANNOTATED_DATASET, require_description=True)
    processed_entries = load_source_dataset(PROCESSED_DATASET, require_description=False)

    # Combined pool: annotated first (higher quality), then processed
    all_source = annotated_entries + processed_entries

    # ── Collect candidates per bucket ─────────────────────────────────────
    candidates = {"designer": [], "optimizer": [], "validator": []}
    seen_hashes = set(existing_hashes)

    for raw, bucket in all_source:
        h = compute_hash(raw.get("code", ""))
        if h in seen_hashes:
            continue
        seen_hashes.add(h)
        candidates[bucket].append(raw)

    print(f"\nNew unique candidates available:")
    print(f"  Designer:  {len(candidates['designer'])}")
    print(f"  Optimizer: {len(candidates['optimizer'])}")
    print(f"  Validator: {len(candidates['validator'])}")

    # ── If optimizer/validator don't have enough, borrow from designer ────
    # Designer pool is always largest; we'll reclassify borderline entries
    remaining_designer = candidates["designer"]

    def borrow_from_designer(need: int, current_candidates: list) -> list:
        """Take up to `need` entries from designer pool if bucket is short."""
        shortfall = need - len(current_candidates)
        if shortfall <= 0:
            return current_candidates
        borrowed = remaining_designer[:shortfall]
        del remaining_designer[:shortfall]
        return current_candidates + borrowed

    if len(candidates["optimizer"]) < need_optimizer:
        candidates["optimizer"] = borrow_from_designer(need_optimizer, candidates["optimizer"])
    if len(candidates["validator"]) < need_validator:
        candidates["validator"] = borrow_from_designer(need_validator, candidates["validator"])

    # ── Backup existing files ─────────────────────────────────────────────
    print("\nBacking up existing knowledge base files...")
    for kb_file in [DESIGNER_KB, OPTIMIZER_KB, VALIDATOR_KB]:
        if kb_file.exists():
            backup_file(kb_file)

    # ── Write new entries ─────────────────────────────────────────────────
    def write_new_entries(kb_file: Path, bucket: str, pool: list, need: int,
                          builder_annotated, builder_processed):
        if need == 0:
            print(f"\n  [{bucket}] Target already met, skipping.")
            return 0

        to_add = pool[:need]
        actual = 0

        with open(kb_file, "a", encoding="utf-8") as f:
            for i, raw in enumerate(to_add):
                source = raw.get("source", "")
                if source == "github" and raw.get("description", ""):
                    # annotated dataset entry
                    entry = builder_annotated(raw, cur_counts[bucket] + i + 1, bucket)
                else:
                    # processed dataset entry
                    entry = builder_processed(raw, cur_counts[bucket] + i + 1, bucket)
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                actual += 1

        return actual

    cur_counts = {
        "designer":  cur_designer,
        "optimizer": cur_optimizer,
        "validator": cur_validator,
    }

    print("\nWriting new entries...")

    added_designer  = write_new_entries(
        DESIGNER_KB, "designer",  candidates["designer"],  need_designer,
        build_new_entry_from_annotated, build_new_entry_from_processed
    )
    added_optimizer = write_new_entries(
        OPTIMIZER_KB, "optimizer", candidates["optimizer"], need_optimizer,
        build_new_entry_from_annotated, build_new_entry_from_processed
    )
    added_validator = write_new_entries(
        VALIDATOR_KB, "validator", candidates["validator"], need_validator,
        build_new_entry_from_annotated, build_new_entry_from_processed
    )

    # ── Final summary ─────────────────────────────────────────────────────
    final_designer  = count_existing(DESIGNER_KB)
    final_optimizer = count_existing(OPTIMIZER_KB)
    final_validator = count_existing(VALIDATOR_KB)
    final_total     = final_designer + final_optimizer + final_validator

    print("\n" + "=" * 60)
    print("  Expansion Complete!")
    print("=" * 60)
    print(f"\n  {'Bucket':<12} {'Before':>7} {'Added':>7} {'After':>7} {'Target':>7}")
    print(f"  {'-'*44}")
    print(f"  {'Designer':<12} {cur_designer:>7} {added_designer:>7} {final_designer:>7} {TARGET_DESIGNER:>7}")
    print(f"  {'Optimizer':<12} {cur_optimizer:>7} {added_optimizer:>7} {final_optimizer:>7} {TARGET_OPTIMIZER:>7}")
    print(f"  {'Validator':<12} {cur_validator:>7} {added_validator:>7} {final_validator:>7} {TARGET_VALIDATOR:>7}")
    print(f"  {'-'*44}")
    print(f"  {'TOTAL':<12} {cur_designer+cur_optimizer+cur_validator:>7} "
          f"{added_designer+added_optimizer+added_validator:>7} {final_total:>7} "
          f"{TARGET_DESIGNER+TARGET_OPTIMIZER+TARGET_VALIDATOR:>7}")
    print()

    if final_designer >= TARGET_DESIGNER and final_optimizer >= TARGET_OPTIMIZER and final_validator >= TARGET_VALIDATOR:
        print("  [OK] All targets achieved!")
    else:
        print("  [WARN] Some targets not fully met (insufficient unique source data).")
        print("    Consider adding more source datasets or lowering thresholds.")


if __name__ == "__main__":
    expand_knowledge_base()
