"""
Runs end-to-end recommendation pipeline evaluation.
Usage:
  python -m eval.scripts.run_recommendations
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

eval_root = Path(__file__).resolve().parent.parent
backend_dir = eval_root.parent
root_dir = backend_dir.parent
for p in (root_dir, backend_dir, eval_root):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from eval.src.data_loader import GoldenDataLoader
from eval.src.recommendation_evaluator import RecommendationEvaluator


def main():
    eval_root = Path(__file__).resolve().parent.parent
    loader = GoldenDataLoader(dataset_dir=eval_root / "datasets")
    print("=" * 60)
    print(" CAREERCONNECT RECOMMENDATION BENCHMARK")
    print("=" * 60)

    evaluator = RecommendationEvaluator(loader=loader)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output_path = eval_root / "artifacts" / f"recommendation_results_{timestamp}.jsonl"
    summary, results = evaluator.evaluate_all(
        output_artifact_path=output_path
    )

    print(f"Total Evaluated Candidates: {summary.total_candidates}")
    print(f"Precision@3: {summary.mean_precision_at_3:.4f}")
    print(f"Precision@5: {summary.mean_precision_at_5:.4f}")
    print(f"Recall@3: {summary.mean_recall_at_3:.4f}")
    print(f"Recall@5: {summary.mean_recall_at_5:.4f}")
    print(f"HitRate@5: {summary.mean_hit_rate_at_5:.4f}")
    print(f"MRR: {summary.mean_mrr:.4f}")
    print(f"nDCG@5: {summary.mean_ndcg_at_5:.4f}")
    print(f"Duplicate Rate: {summary.duplicate_rate:.4f}")
    print(f"Category Coverage: {summary.mean_category_coverage:.4f}")
    print(f"Skill Compatibility: {summary.mean_skill_compatibility:.4f}")
    print(f"Seniority Compatibility: {summary.mean_seniority_compatibility:.4f}")
    print(f"Mean Latency: {summary.mean_latency_ms:.2f} ms")
    print(f"Per-candidate results: {output_path}")
    print("Ranking stages (P@5 / R@5 / HitRate@5 / MRR / nDCG@5):")
    for stage_name, metrics in summary.stage_metrics.items():
        print(
            f"  {stage_name}: {metrics.precision_at_5:.4f} / "
            f"{metrics.recall_at_5:.4f} / {metrics.hit_rate_at_5:.4f} / "
            f"{metrics.mrr:.4f} / {metrics.ndcg_at_5:.4f}"
        )


if __name__ == "__main__":
    main()
