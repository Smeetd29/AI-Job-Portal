"""
Master entrypoint to run all evaluation suites.
Usage:
  python -m eval.scripts.run_all
  python -m eval.scripts.run_all --validate-only
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add repo root, backend, and eval to sys.path
eval_root = Path(__file__).resolve().parent.parent
backend_dir = eval_root.parent
root_dir = backend_dir.parent
for p in (root_dir, backend_dir, eval_root):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from eval.src.dataset_validation import DatasetValidator
from eval.src.runner import MasterEvaluationRunner


def main():
    parser = argparse.ArgumentParser(description="CareerConnect Master Evaluation Runner")
    parser.add_argument("--validate-only", action="store_true", help="Only validate golden datasets")
    args = parser.parse_args()

    eval_root = Path(__file__).resolve().parent.parent

    if args.validate_only:
        validator = DatasetValidator(dataset_dir=eval_root / "datasets")
        counts = validator.validate_all()
        print("Dataset Validation PASSED!")
        for k, v in counts.items():
            print(f"  - {k}: {v}")
        return

    runner = MasterEvaluationRunner(eval_root=eval_root)
    runner.run_full_suite()


if __name__ == "__main__":
    main()
