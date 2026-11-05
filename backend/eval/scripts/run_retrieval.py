"""
Runs dense retrieval evaluation over golden jobs and resumes.
Usage:
  python -m eval.scripts.run_retrieval
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
from eval.src.optimization import RetrievalOptimizer
from eval.src.retrieval_evaluator import RetrievalEvaluator


def main():
    eval_root = Path(__file__).resolve().parent.parent
    loader = GoldenDataLoader(dataset_dir=eval_root / "datasets")
    print("=" * 60)
    print(" CAREERCONNECT RETRIEVAL BENCHMARK")
    print("=" * 60)

    evaluator = RetrievalEvaluator(loader=loader)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    output_path = eval_root / "artifacts" / f"retrieval_results_{timestamp}.jsonl"
    summary, results = evaluator.evaluate_all(
        output_artifact_path=output_path
    )

    print(f"Total Evaluated Queries: {summary.total_queries}")
    print(f"Precision@3: {summary.mean_precision_at_3:.4f}")
    print(f"Precision@5: {summary.mean_precision_at_5:.4f}")
    print(f"Precision@10: {summary.mean_precision_at_10:.4f}")
    print(f"Recall@3: {summary.mean_recall_at_3:.4f}")
    print(f"Recall@5: {summary.mean_recall_at_5:.4f}")
    print(f"Recall@10: {summary.mean_recall_at_10:.4f}")
    print(f"HitRate@5: {summary.mean_hit_rate_at_5:.4f}")
    print(f"MRR: {summary.mean_mrr:.4f}")
    print(f"nDCG@5: {summary.mean_ndcg_at_5:.4f}")
    print(f"Mean Latency: {summary.mean_latency_ms:.2f} ms")
    print(f"Per-query results: {output_path}")


if __name__ == "__main__":
    main()
