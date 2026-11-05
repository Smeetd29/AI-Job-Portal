"""
Runs recommendation explanation generation and DeepEval groundedness evaluation.
Usage:
  python -m eval.scripts.run_generation
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
from eval.src.generation_evaluator import GenerationEvaluator


def main():
    eval_root = Path(__file__).resolve().parent.parent
    loader = GoldenDataLoader(dataset_dir=eval_root / "datasets")
    print("=" * 60)
    print(" CAREERCONNECT GENERATION & EXPLANATION BENCHMARK")
    print("=" * 60)

    evaluator = GenerationEvaluator(loader=loader)
    summary, results = evaluator.evaluate_all(
        output_artifact_path=eval_root / "artifacts" / "generation_results.jsonl",
        max_cases=50,
    )

    print(f"Total Evaluated Cases: {summary.total_evaluations}")
    print(f"Mean Faithfulness: {summary.mean_faithfulness:.4f}")
    print(f"Mean Answer Relevancy: {summary.mean_relevancy:.4f}")
    print(f"Mean GEval Quality: {summary.mean_geval:.4f}")
    print(f"Grounded Skills Rate: {summary.mean_grounded_skills_rate * 100:.1f}%")
    print(f"Grounded Gaps Rate: {summary.mean_grounded_gaps_rate * 100:.1f}%")
    print(f"Overall Pass Rate: {summary.pass_rate * 100:.1f}%")
    print(f"Mean Latency: {summary.mean_latency_ms:.2f} ms")


if __name__ == "__main__":
    main()
