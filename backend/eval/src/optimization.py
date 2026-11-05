from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from eval.src.data_loader import GoldenDataLoader
from eval.src.retrieval_evaluator import RetrievalBenchmarkSummary, RetrievalEvaluator
from eval.src.retrieval_evaluator import (
    calculate_hit_rate_at_k,
    calculate_mrr,
    calculate_ndcg_at_k,
    calculate_precision_at_k,
    calculate_recall_at_k,
)


@dataclass
class OptimizationExperimentResult:
    experiment_id: str
    strategy: str
    description: str
    top_k: int
    mean_precision_at_5: float
    mean_recall_at_5: float
    mean_hit_rate_at_5: float
    mean_mrr: float
    mean_ndcg_at_5: float
    mean_latency_ms: float
    summary: RetrievalBenchmarkSummary


@dataclass
class RetrievalDepthExperimentResult:
    retrieval_k: int
    total_queries: int
    mean_precision_at_k: float
    mean_recall_at_k: float
    mean_hit_rate_at_k: float
    mean_mrr: float
    mean_ndcg_at_5: float
    mean_latency_ms: float
    mean_candidates_returned: float
    warmup_latency_ms: float
    micro_precision_at_k: float
    micro_recall_at_k: float


class RetrievalOptimizer:
    """Runs systematic retrieval experiments across query representation and indexing configurations."""

    def __init__(self, loader: Optional[GoldenDataLoader] = None):
        self.loader = loader or GoldenDataLoader()
        self.evaluator = RetrievalEvaluator(loader=self.loader)

    def run_query_representation_experiments(self) -> List[OptimizationExperimentResult]:
        """
        Compares:
          1. Baseline: Raw truncated resume text (first 400 characters).
          2. Skills-only: Comma-separated normalized candidate skills.
          3. Section-aware: Preferred roles + Canonical Skills + Candidate Summary.
        """
        experiments = [
            ("exp_1_raw_resume_baseline", "raw_resume", "Raw resume text prefix (first 400 chars)", 10),
            ("exp_2_skills_only", "skills_only", "Extracted canonical skills only", 10),
            ("exp_3_section_aware_optimized", "section_aware", "Preferred roles + Top skills + Summary section", 10),
        ]

        results = []
        for exp_id, strategy, desc, top_k in experiments:
            exp_res = self._run_single_experiment(exp_id, strategy, desc, top_k)
            results.append(exp_res)

        return results

    def run_retrieval_depth_experiments(
        self,
        k_values: Tuple[int, ...] = (10, 20, 50),
    ) -> List[RetrievalDepthExperimentResult]:
        """Measure dense retrieval at each available depth without writing over artifacts."""
        self.evaluator._ensure_pipeline()
        resume_ids = [
            resume_id
            for resume_id in sorted(self.evaluator.resumes)
            if resume_id in self.evaluator.relevance_by_resume
        ]
        if not resume_ids:
            return []

        results = []
        for requested_k in k_values:
            if requested_k <= 0:
                raise ValueError("Retrieval depth values must be positive.")
            effective_k = min(requested_k, len(self.evaluator.jobs))
            warmup = self.evaluator.evaluate_query(resume_ids[0], top_k=effective_k)
            query_results = [
                self.evaluator.evaluate_query(resume_id, top_k=effective_k)
                for resume_id in resume_ids
            ]

            def macro_mean(values: List[float]) -> float:
                valid = [value for value in values if not math.isnan(value)]
                return float(np.mean(valid)) if valid else 0.0

            total_hits = sum(
                sum(
                    1 for job_id in result.retrieved_job_ids[:effective_k]
                    if job_id in set(result.relevant_job_ids)
                )
                for result in query_results
            )
            total_relevant = sum(len(result.relevant_job_ids) for result in query_results)
            results.append(RetrievalDepthExperimentResult(
                retrieval_k=effective_k,
                total_queries=len(query_results),
                mean_precision_at_k=macro_mean([
                    calculate_precision_at_k(
                        result.retrieved_job_ids,
                        set(result.relevant_job_ids),
                        effective_k,
                    )
                    for result in query_results
                ]),
                mean_recall_at_k=macro_mean([
                    calculate_recall_at_k(
                        result.retrieved_job_ids,
                        set(result.relevant_job_ids),
                        effective_k,
                    )
                    for result in query_results
                ]),
                mean_hit_rate_at_k=macro_mean([
                    calculate_hit_rate_at_k(
                        result.retrieved_job_ids,
                        set(result.relevant_job_ids),
                        effective_k,
                    )
                    for result in query_results
                ]),
                mean_mrr=macro_mean([
                    calculate_mrr(result.retrieved_job_ids, set(result.relevant_job_ids))
                    for result in query_results
                ]),
                mean_ndcg_at_5=macro_mean([
                    result.ndcg_at_5 for result in query_results
                ]),
                mean_latency_ms=macro_mean([
                    result.latency_ms for result in query_results
                ]),
                mean_candidates_returned=macro_mean([
                    float(len(result.retrieved_job_ids)) for result in query_results
                ]),
                warmup_latency_ms=warmup.latency_ms,
                micro_precision_at_k=(
                    total_hits / float(len(query_results) * effective_k)
                    if query_results else 0.0
                ),
                micro_recall_at_k=(
                    total_hits / float(total_relevant) if total_relevant else 0.0
                ),
            ))
        return results

    def _run_single_experiment(
        self,
        exp_id: str,
        strategy: str,
        description: str,
        top_k: int,
    ) -> OptimizationExperimentResult:
        self.evaluator._ensure_pipeline()
        query_results = []

        for resume_id, resume in self.evaluator.resumes.items():
            if resume_id not in self.evaluator.relevance_by_resume:
                continue

            if strategy == "raw_resume":
                q_text = resume.resume_text[:400]
            elif strategy == "skills_only":
                q_text = ", ".join(resume.skills)
            elif strategy == "section_aware":
                roles = ", ".join(resume.candidate_profile.get("preferred_roles", []))
                skills = ", ".join(resume.skills[:8])
                q_text = f"{roles}. Key skills: {skills}. Background: {resume.resume_text[:300]}"
            else:
                q_text = resume.resume_text[:400]

            res = self.evaluator.evaluate_query(resume_id, query_text=q_text, top_k=top_k)
            query_results.append(res)

        import math
        import numpy as np
        def safe_mean(values: List[float]) -> float:
            valid = [v for v in values if not math.isnan(v)]
            return float(np.mean(valid)) if valid else 0.0

        summary = RetrievalBenchmarkSummary(
            total_queries=len(query_results),
            mean_precision_at_3=safe_mean([r.precision_at_3 for r in query_results]),
            mean_precision_at_5=safe_mean([r.precision_at_5 for r in query_results]),
            mean_precision_at_10=safe_mean([r.precision_at_10 for r in query_results]),
            mean_recall_at_3=safe_mean([r.recall_at_3 for r in query_results]),
            mean_recall_at_5=safe_mean([r.recall_at_5 for r in query_results]),
            mean_recall_at_10=safe_mean([r.recall_at_10 for r in query_results]),
            mean_hit_rate_at_5=safe_mean([r.hit_rate_at_5 for r in query_results]),
            mean_mrr=safe_mean([r.mrr for r in query_results]),
            mean_ndcg_at_5=safe_mean([r.ndcg_at_5 for r in query_results]),
            mean_latency_ms=safe_mean([r.latency_ms for r in query_results]),
        )

        return OptimizationExperimentResult(
            experiment_id=exp_id,
            strategy=strategy,
            description=description,
            top_k=top_k,
            mean_precision_at_5=summary.mean_precision_at_5,
            mean_recall_at_5=summary.mean_recall_at_5,
            mean_hit_rate_at_5=summary.mean_hit_rate_at_5,
            mean_mrr=summary.mean_mrr,
            mean_ndcg_at_5=summary.mean_ndcg_at_5,
            mean_latency_ms=summary.mean_latency_ms,
            summary=summary,
        )
