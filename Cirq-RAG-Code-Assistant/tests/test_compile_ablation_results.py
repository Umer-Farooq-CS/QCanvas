import json
from pathlib import Path
import pytest


def _find_results_file():
    candidates = [
        Path("Cirq-RAG-Code-Assistant") / "results" / "ablation_results_step2.json",
        Path("Cirq-RAG-Code-Assistant") / "results" / "ablation_results.json",
        Path("results") / "ablation_results_step2.json",
        Path("results") / "ablation_results.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _iter_codes(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "code" and isinstance(v, str):
                yield v
            else:
                yield from _iter_codes(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iter_codes(item)


def test_compile_generated_code():
    results_path = _find_results_file()
    if results_path is None:
        pytest.skip(
            "No ablation results file found. Run the ablation (Notebook 15 or CLI) to produce results/ablation_results_step2.json"
        )

    data = json.loads(results_path.read_text(encoding="utf-8"))

    failures = []
    total = 0
    for code in _iter_codes(data):
        total += 1
        try:
            compile(code, "<generated>", "exec")
        except Exception as e:
            failures.append({"error": repr(e), "snippet_preview": code[:200]})

    assert total > 0, "No code snippets found in the results file."
    if failures:
        msg_lines = [f"{len(failures)} of {total} snippets failed to compile:"]
        for i, f in enumerate(failures[:10], 1):
            msg_lines.append(f"{i}. {f['error']} -- preview: {f['snippet_preview']}")
        if len(failures) > 10:
            msg_lines.append("...more failures omitted")
        pytest.fail("\n".join(msg_lines))
