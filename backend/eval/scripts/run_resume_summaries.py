"""
Runs candidate resume summarization and factual consistency evaluation.
Usage:
  python -m eval.scripts.run_resume_summaries
"""

from __future__ import annotations

import sys
from pathlib import Path

eval_root = Path(__file__).resolve().parent.parent
backend_dir = eval_root.parent
root_dir = backend_dir.parent
for p in (root_dir, backend_dir, eval_root):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from eval.src.data_loader import GoldenDataLoader
from eval.src.resume_summary_evaluator import ResumeSummaryEvaluator


def main():
    eval_root = Path(__file__).resolve().parent.parent
    loader = GoldenDataLoader(dataset_dir=eval_root / "datasets")
    print("=" * 60)
    print(" CAREERCONNECT RESUME SUMMARIZATION BENCHMARK")
    print("=" * 60)

    evaluator = ResumeSummaryEvaluator(loader=loader)
    summary, results = evaluator.evaluate_all(
        output_artifact_path=eval_root / "artifacts" / "summary_results.jsonl"
    )

    print(f"Total Evaluated Summaries: {summary.total_summaries}")
    print(f"Mean Faithfulness: {summary.mean_faithfulness:.4f}")
    print(f"Mean Answer Relevancy: {summary.mean_relevancy:.4f}")
    print(f"Mean GEval Quality: {summary.mean_geval:.4f}")
    print(f"Schema Validity Rate: {summary.schema_validity_rate * 100:.1f}%")
    print(f"Hallucination Rate: {summary.hallucination_rate * 100:.1f}%")
    print(f"Factual Completeness Rate: {summary.factual_completeness_rate * 100:.1f}%")
    print(f"Overall Pass Rate: {summary.pass_rate * 100:.1f}%")
    print(f"Mean Latency: {summary.mean_latency_ms:.2f} ms")


if __name__ == "__main__":
    main()
