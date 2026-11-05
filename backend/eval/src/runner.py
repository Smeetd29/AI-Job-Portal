from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from eval.src.data_loader import GoldenDataLoader
from eval.src.dataset_validation import DatasetValidator
from eval.src.generation_evaluator import GenerationEvaluator
from eval.src.optimization import RetrievalOptimizer
from eval.src.recommendation_evaluator import RecommendationEvaluator
from eval.src.resume_summary_evaluator import ResumeSummaryEvaluator
from eval.src.retrieval_evaluator import RetrievalEvaluator


class MasterEvaluationRunner:
    """Master orchestrator for CareerConnect's DeepEval & IR evaluation framework."""

    def __init__(self, eval_root: Optional[Path] = None):
        self.eval_root = eval_root or Path(__file__).resolve().parent.parent
        self.datasets_dir = self.eval_root / "datasets"
        self.artifacts_dir = self.eval_root / "artifacts"
        self.loader = GoldenDataLoader(dataset_dir=self.datasets_dir)

    def run_full_suite(self, deleted_files: Optional[List[str]] = None) -> Dict[str, Any]:
        print("=" * 70)
        print(" CAREERCONNECT EVALUATION & DEEPEVAL SUITE")
        print("=" * 70)

        # 1. Validate Datasets
        print("\n[1/6] Validating Golden Datasets...")
        validator = DatasetValidator(dataset_dir=self.datasets_dir)
        dataset_counts = validator.validate_all()
        print(f"  -> Validated {dataset_counts['jobs_count']} jobs, {dataset_counts['resumes_count']} resumes, "
              f"{dataset_counts['recommendations_count']} judgments, {dataset_counts['summaries_count']} summaries.")

        # 2. Retrieval Evaluation & Optimization
        print("\n[2/6] Evaluating Retrieval & Query Optimization Grid...")
        optimizer = RetrievalOptimizer(loader=self.loader)
        experiments = optimizer.run_query_representation_experiments()

        baseline_exp = experiments[0]
        optimized_exp = experiments[-1]
        print(f"  -> Baseline Retrieval Recall@5: {baseline_exp.mean_recall_at_5:.4f}, nDCG@5: {baseline_exp.mean_ndcg_at_5:.4f}")
        print(f"  -> Optimized Retrieval Recall@5: {optimized_exp.mean_recall_at_5:.4f}, nDCG@5: {optimized_exp.mean_ndcg_at_5:.4f}")

        # Save retrieval artifacts
        retrieval_evaluator = RetrievalEvaluator(loader=self.loader)
        _, query_results = retrieval_evaluator.evaluate_all(
            output_artifact_path=self.artifacts_dir / "retrieval_results.jsonl"
        )

        # 3. End-to-End Recommendation Evaluation
        print("\n[3/6] Evaluating End-to-End Job Recommendation Pipeline...")
        rec_evaluator = RecommendationEvaluator(loader=self.loader)
        rec_summary, _ = rec_evaluator.evaluate_all(
            output_artifact_path=self.artifacts_dir / "recommendation_results.jsonl"
        )
        print(f"  -> Recommendation Precision@5: {rec_summary.mean_precision_at_5:.4f}, Recall@5: {rec_summary.mean_recall_at_5:.4f}, "
              f"nDCG@5: {rec_summary.mean_ndcg_at_5:.4f}, Duplicate Rate: {rec_summary.duplicate_rate:.4f}")

        # 4. Resume Summarization Evaluation
        print("\n[4/6] Evaluating Resume Summarization & Factual Consistency...")
        sum_evaluator = ResumeSummaryEvaluator(loader=self.loader)
        sum_summary, _ = sum_evaluator.evaluate_all(
            output_artifact_path=self.artifacts_dir / "summary_results.jsonl"
        )
        faith_str = f"{sum_summary.mean_faithfulness:.4f}" if sum_summary.mean_faithfulness is not None else "BLOCKED (No API Key)"
        print(f"  -> Context Groundedness: {sum_summary.mean_context_groundedness:.4f}, DeepEval Faithfulness: {faith_str}, "
              f"Hallucination Rate: {sum_summary.hallucination_rate * 100:.1f}%, Deterministic Pass Rate: {sum_summary.deterministic_pass_rate * 100:.1f}%")

        # 5. Recommendation Explanation & Generation Evaluation
        print("\n[5/6] Evaluating Recommendation Explanation Groundedness...")
        gen_evaluator = GenerationEvaluator(loader=self.loader)
        gen_summary, _ = gen_evaluator.evaluate_all(
            output_artifact_path=self.artifacts_dir / "generation_results.jsonl",
            max_cases=50,
        )
        gen_faith_str = f"{gen_summary.mean_faithfulness:.4f}" if gen_summary.mean_faithfulness is not None else "BLOCKED (No API Key)"
        print(f"  -> Token Groundedness: {gen_summary.mean_token_groundedness:.4f}, DeepEval Faithfulness: {gen_faith_str}, "
              f"Grounded Skills Rate: {gen_summary.mean_grounded_skills_rate * 100:.1f}%, Grounded Gaps Rate: {gen_summary.mean_grounded_gaps_rate * 100:.1f}%")

        # 6. Final Summary Artifacts
        print("\n[6/6] Generating Master Evaluation Summary Artifacts...")
        final_deleted = deleted_files or []

        # Machine-readable summary artifact
        summary_payload = {
            "retrieval_baseline": asdict(baseline_exp.summary),
            "retrieval_optimized": asdict(optimized_exp.summary),
            "recommendation": asdict(rec_summary),
            "resume_summary": asdict(sum_summary),
            "generation": asdict(gen_summary),
            "deleted_legacy_files": final_deleted,
        }
        with open(self.artifacts_dir / "master_summary.json", "w", encoding="utf-8") as f:
            json.dump(summary_payload, f, indent=2)

        print("\nMaster Evaluation Suite Completed Successfully!")
        return summary_payload
