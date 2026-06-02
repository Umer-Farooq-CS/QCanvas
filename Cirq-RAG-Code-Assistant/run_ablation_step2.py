"""Run AblationStudy (Step 2) and save results to results/ablation_results_step2.json

This script adjusts sys.path so the local `src` package can be imported when
running from the repo root.
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
SRC_PATH = REPO_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from evaluation.ablation import AblationStudy


def main():
    study = AblationStudy()
    results = study.run_study(num_trials=5)
    out = REPO_ROOT / "results" / "ablation_results_step2.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    study.save_results(out, results)
    print(f"Saved ablation results to: {out}")


if __name__ == "__main__":
    main()
