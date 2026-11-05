"""
Candidate-Level Cross-Validation and Bootstrap Confidence Interval Module.

Ensures:
1. Strict candidate-level partitioning: all interactions/judgments for a candidate belong to exactly one fold.
2. Zero candidate leakage across train/validation/test folds.
3. Computation of theoretical ceilings, normalized metrics, nDCG@5/10, MAP, R-Precision, and stage funnels.
4. Non-parametric bootstrap 95% confidence intervals for all metrics.
5. Real CV retraining: for each fold, retrain LightGBM LambdaMART on train folds, tune on validation fold,
   and evaluate on the held-out fold, reporting alongside the fixed-model baseline.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
import lightgbm as lgb
import numpy as np

from eval.src.data_loader import GoldenDataLoader, SyntheticBenchmarkLoader
from eval.src.retrieval_evaluator import bootstrap_ci
from eval.src.recommendation_evaluator import (
    RecommendationCaseResult,
    RecommendationEvaluator,
)
from application.ai.ranking import LightGBMRanker, MatchFeatures


def _safe_mean(values: Sequence[float]) -> float:
    valid = [v for v in values if not math.isnan(v)]
    return float(np.mean(valid)) if valid else 0.0


def _safe_std(values: Sequence[float]) -> float:
    valid = [v for v in values if not math.isnan(v)]
    return float(np.std(valid, ddof=1)) if len(valid) > 1 else 0.0


@dataclass
class FoldMetrics:
    fold_index: int
    num_candidates: int
    candidate_ids: List[str]
    # Headline metrics
    ndcg_at_5: float
    map: float
    normalized_precision_at_5: float
    normalized_recall_at_5: float
    # Standard metrics
    precision_at_5: float
    recall_at_5: float
    ndcg_at_10: float
    r_precision: float
    recall_at_20: float
    recall_at_50: float
    recall_at_100: float
    # Unthresholded metrics
    unthresholded_ndcg_at_5: float
    unthresholded_precision_at_5: float
    unthresholded_recall_at_5: float
    # Stage progression (mean rank of relevant jobs across stages)
    retrieval_mean_rank: float
    rerank_mean_rank: float
    score_mean_rank: float
    # Losses & Latency
    total_lost_at_retrieval: int
    total_lost_at_threshold: int
    mean_latency_ms: float
    # Demoted metrics
    mrr: float = 1.0
    hit_rate_at_5: float = 1.0


@dataclass
class MetricSummary:
    mean: float
    std: float
    ci_lower: float
    ci_upper: float

    def format_report(self) -> str:
        return f"{self.mean:.4f} ± {self.std:.4f} [95% CI: {self.ci_lower:.4f}, {self.ci_upper:.4f}]"


@dataclass
class CrossValidationSummary:
    n_folds: int
    total_candidates: int
    candidate_pool: str
    model_mode: str  # 'retrained_cv' or 'fixed_baseline'
    folds: List[FoldMetrics]
    # Headline metrics
    ndcg_at_5: MetricSummary
    map: MetricSummary
    normalized_precision_at_5: MetricSummary
    normalized_recall_at_5: MetricSummary
    # Diagnostic metrics
    precision_at_5: MetricSummary
    recall_at_5: MetricSummary
    ndcg_at_10: MetricSummary
    r_precision: MetricSummary
    recall_at_20: MetricSummary
    recall_at_50: MetricSummary
    recall_at_100: MetricSummary
    unthresholded_ndcg_at_5: MetricSummary
    unthresholded_precision_at_5: MetricSummary
    unthresholded_recall_at_5: MetricSummary
    retrieval_mean_rank: MetricSummary
    rerank_mean_rank: MetricSummary
    score_mean_rank: MetricSummary
    latency_ms: MetricSummary
    # Demoted metrics
    mrr: MetricSummary
    hit_rate_at_5: MetricSummary
    funnel_summary: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CrossValidationComparison:
    candidate_pool: str
    n_folds: int
    retrained: CrossValidationSummary
    fixed: CrossValidationSummary


def partition_candidates_kfold(
    candidate_ids: Sequence[str],
    n_folds: int = 5,
    seed: int = 42,
) -> List[List[str]]:
    """
    Partitions candidate IDs into K disjoint folds deterministically.
    """
    if n_folds < 2:
        raise ValueError(f"n_folds must be >= 2, got {n_folds}")
    sorted_cands = sorted(candidate_ids)
    rng = np.random.default_rng(seed)
    shuffled = list(sorted_cands)
    rng.shuffle(shuffled)

    folds: List[List[str]] = [[] for _ in range(n_folds)]
    for idx, cid in enumerate(shuffled):
        folds[idx % n_folds].append(cid)
    return folds


class UnifiedCandidateEvaluator:
    """
    Evaluates candidates across both golden and synthetic datasets using the production recommendation pipeline.
    """

    def __init__(self, min_match: int = 50):
        self.min_match = min_match
        self.golden_loader = GoldenDataLoader()
        self.synthetic_loader = SyntheticBenchmarkLoader()

        self.golden_jobs = self.golden_loader.load_jobs()
        self.golden_resumes = self.golden_loader.load_resumes()
        self.golden_recs = self.golden_loader.load_recommendations()

        self.synthetic_jobs = self.synthetic_loader.load_jobs()
        self.synthetic_resumes = self.synthetic_loader.load_resumes()
        self.synthetic_recs = self.synthetic_loader.load_recommendations()

        # Build candidate relevance dictionaries
        self.relevance_by_candidate: Dict[str, Dict[str, int]] = {}
        for r in self.golden_recs:
            if r.resume_id not in self.relevance_by_candidate:
                self.relevance_by_candidate[r.resume_id] = {}
            self.relevance_by_candidate[r.resume_id][r.job_id] = r.relevance

        for r in self.synthetic_recs:
            if r.resume_id not in self.relevance_by_candidate:
                self.relevance_by_candidate[r.resume_id] = {}
            self.relevance_by_candidate[r.resume_id][r.job_id] = r.relevance

        # Evaluators
        self._golden_evaluator = RecommendationEvaluator(loader=self.golden_loader, min_match=min_match)
        self._synthetic_evaluator = RecommendationEvaluator(loader=self.synthetic_loader, min_match=min_match)

    def evaluate_candidate(
        self,
        candidate_id: str,
        retrieval_k: int = 100,
        custom_ranker: Optional[Any] = None,
    ) -> RecommendationCaseResult:
        if candidate_id in self.golden_resumes:
            return self._golden_evaluator.evaluate_candidate(
                candidate_id,
                retrieval_k=retrieval_k,
                custom_ranker=custom_ranker,
            )
        elif candidate_id in self.synthetic_resumes:
            return self._synthetic_evaluator.evaluate_candidate(
                candidate_id,
                retrieval_k=retrieval_k,
                custom_ranker=custom_ranker,
            )
        else:
            raise KeyError(f"Candidate {candidate_id} not found in golden or synthetic datasets.")


class CrossValidationTrainer:
    """
    Extracts tabular ranking features for candidate-job pairs and trains
    fold-specific LightGBM LambdaMART rankers with zero test leakage.
    """

    def __init__(self, evaluator: UnifiedCandidateEvaluator):
        self.evaluator = evaluator
        self.evaluator._golden_evaluator._ensure_pipeline()
        self.pipeline = self.evaluator._golden_evaluator.pipeline
        self._cache: Dict[str, Tuple[List[List[float]], List[int]]] = {}
        self._parsed_jobs_cache: Dict[str, Any] = {}
        self._job_embs_cache: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}

    def _get_job_info(self, job: Any) -> Tuple[Any, np.ndarray, np.ndarray]:
        jid = str(job.job_id)
        if jid not in self._parsed_jobs_cache:
            c_job = self.pipeline.cleaner(job.description)
            j_doc = self.pipeline.job_parser.parse(clean_text=c_job, title=job.title, raw_text=job.description)
            norm = self.pipeline.normalizer.normalize_list
            ex = self.pipeline.skill_extractor.extract
            if hasattr(job, "required_skills") and job.required_skills:
                j_doc.required_skill_candidates = norm(job.required_skills)
            else:
                j_doc.required_skill_candidates = norm(ex(j_doc.required_skills_section or c_job))
            if hasattr(job, "preferred_skills") and job.preferred_skills:
                j_doc.preferred_skill_candidates = norm(job.preferred_skills)
            else:
                j_doc.preferred_skill_candidates = norm(ex(j_doc.preferred_skills_section or "")) if j_doc.preferred_skills_section else []
            j_doc.required_years = self.pipeline.experience_extractor.extract(c_job)
            j_doc.required_degree_level = self.pipeline.education_extractor.extract(c_job)
            j_doc.seniority_label = self.pipeline.seniority_extractor.extract(
                f"{job.title}\n{c_job[:400]}",
                years_experience=j_doc.required_years,
                degree_level=j_doc.required_degree_level,
            )
            self._parsed_jobs_cache[jid] = j_doc
            j_text = f"{job.title}. {', '.join(j_doc.required_skill_candidates)}. {c_job[:600]}"
            title_text = f"{job.title} {job.category}"
            embs = self.pipeline.embedding.embed_batch([j_text, title_text])
            self._job_embs_cache[jid] = (embs[0], embs[1])

        return self._parsed_jobs_cache[jid], self._job_embs_cache[jid][0], self._job_embs_cache[jid][1]

    def extract_features_for_candidate(self, cid: str) -> Tuple[List[List[float]], List[int]]:
        if cid in self._cache:
            return self._cache[cid]

        if cid in self.evaluator.golden_resumes:
            r = self.evaluator.golden_resumes[cid]
            jobs_dict = self.evaluator.golden_jobs
            recs = [rec for rec in self.evaluator.golden_recs if rec.resume_id == cid]
        elif cid in self.evaluator.synthetic_resumes:
            r = self.evaluator.synthetic_resumes[cid]
            jobs_dict = self.evaluator.synthetic_jobs
            recs = [rec for rec in self.evaluator.synthetic_recs if rec.resume_id == cid]
        else:
            return ([], [])

        cleaned = self.pipeline.cleaner(r.resume_text)
        r_doc = self.pipeline.resume_parser.parse(cleaned, raw_text=r.resume_text)
        norm = self.pipeline.normalizer.normalize_list
        ex = self.pipeline.skill_extractor.extract
        core = norm(ex(r_doc.skills_section or cleaned))
        proj = norm(ex(r_doc.projects_section or ""))
        r_doc.skill_candidates = core + [s for s in proj if s.lower() not in {c.lower() for c in core}] or norm(ex(cleaned))
        r_doc.years_experience = self.pipeline.experience_extractor.extract(r_doc.experience_section or cleaned)
        r_doc.degree_level = self.pipeline.education_extractor.extract(r_doc.education_section or cleaned)
        r_doc.seniority_label = self.pipeline.seniority_extractor.extract(
            cleaned,
            years_experience=r_doc.years_experience,
            degree_level=r_doc.degree_level,
        )

        cand_sen_str = r_doc.seniority_label.title() if r_doc.seniority_label else "Mid"
        cand_skills_str = ", ".join(r_doc.skill_candidates[:8])
        role_text = f"{cand_sen_str}. {cand_skills_str}. {cleaned[:400]}"
        emb_res = self.pipeline.embedding.embed_text(cleaned[:1000])
        emb_role = self.pipeline.embedding.embed_text(role_text[:600])

        ce_pairs = []
        rec_items = []
        for rec in recs:
            if rec.job_id not in jobs_dict:
                continue
            job = jobs_dict[rec.job_id]
            j_doc, j_emb, j_title_emb = self._get_job_info(job)
            req_skills = ", ".join(j_doc.required_skill_candidates[:10])
            j_sen = j_doc.seniority_label.title() if j_doc.seniority_label else "Any"
            j_exp = f"{j_doc.required_years:.0f} yrs" if j_doc.required_years else "None"
            job_text = f"Role: {job.title}. Level: {j_sen}. Required Exp: {j_exp}. Skills: {req_skills}. {job.description[:400]}"
            cand_text = f"Candidate Seniority: {cand_sen_str}. Experience: {r_doc.years_experience or 0:.0f} yrs. Skills: {cand_skills_str}. {cleaned[:400]}"
            ce_pairs.append((job_text, cand_text))
            rec_items.append((rec, j_doc, j_emb, j_title_emb))

        ce_scores = self.pipeline.reranker.score_pairs(ce_pairs)

        vectors: List[List[float]] = []
        labels: List[int] = []
        for idx, (rec, j_doc, j_emb, j_title_emb) in enumerate(rec_items):
            feats = self.pipeline.feature_extractor.extract(
                resume_doc=r_doc,
                job_doc=j_doc,
                resume_embedding=emb_res,
                job_embedding=j_emb,
                resume_summary_embedding=emb_role,
                job_title_embedding=j_title_emb,
                cross_encoder_score=ce_scores[idx],
            )
            vectors.append(feats.to_vector())
            labels.append(rec.relevance)

        self._cache[cid] = (vectors, labels)
        return (vectors, labels)

    def train_fold(
        self,
        train_cands: Sequence[str],
        val_cands: Sequence[str],
        seed: int = 42,
    ) -> LightGBMRanker:
        X_train: List[List[float]] = []
        y_train: List[int] = []
        group_train: List[int] = []

        for cid in train_cands:
            vecs, labs = self.extract_features_for_candidate(cid)
            if vecs:
                X_train.extend(vecs)
                y_train.extend(labs)
                group_train.append(len(labs))

        X_val: List[List[float]] = []
        y_val: List[int] = []
        group_val: List[int] = []

        for cid in val_cands:
            vecs, labs = self.extract_features_for_candidate(cid)
            if vecs:
                X_val.extend(vecs)
                y_val.extend(labs)
                group_val.append(len(labs))

        params = {
            "objective": "lambdarank",
            "metric": "ndcg",
            "ndcg_eval_at": [3, 5, 10],
            "learning_rate": 0.05,
            "num_leaves": 15,
            "min_data_in_leaf": 2,
            "verbose": -1,
            "seed": seed,
            "deterministic": True,
            "force_row_wise": True,
        }

        train_ds = lgb.Dataset(
            np.array(X_train),
            label=np.array(y_train),
            group=group_train,
            feature_name=MatchFeatures.feature_names(),
        )

        valid_sets = []
        callbacks = []
        if X_val and group_val:
            val_ds = lgb.Dataset(
                np.array(X_val),
                label=np.array(y_val),
                group=group_val,
                reference=train_ds,
            )
            valid_sets = [val_ds]
            callbacks = [lgb.early_stopping(stopping_rounds=10, verbose=False)]

        booster = lgb.train(
            params,
            train_ds,
            valid_sets=valid_sets,
            num_boost_round=40,
            callbacks=callbacks,
        )
        return LightGBMRanker.from_model(
            booster,
            metadata={
                "train_candidates": list(train_cands),
                "val_candidates": list(val_cands),
                "version": f"fold_ranker_seed_{seed}",
            },
        )


def _build_summary(
    all_results: List[RecommendationCaseResult],
    fold_metrics_list: List[FoldMetrics],
    n_folds: int,
    candidate_pool: str,
    model_mode: str,
    seed: int,
) -> CrossValidationSummary:
    def _summarize(values: List[float], fold_values: List[float]) -> MetricSummary:
        mean_val = _safe_mean(values)
        std_val = _safe_std(fold_values)
        ci = bootstrap_ci(values, n_bootstrap=1000, ci=0.95, seed=seed)
        return MetricSummary(
            mean=mean_val,
            std=std_val,
            ci_lower=ci["ci_lower"],
            ci_upper=ci["ci_upper"],
        )

    ret_mean_ranks = [r.funnel.retrieval_mean_rank_relevant for r in all_results if r.funnel]
    rerank_mean_ranks = [r.funnel.rerank_mean_rank_relevant for r in all_results if r.funnel]
    score_mean_ranks = [r.funnel.score_mean_rank_relevant for r in all_results if r.funnel]

    return CrossValidationSummary(
        n_folds=n_folds,
        total_candidates=len(all_results),
        candidate_pool=candidate_pool,
        model_mode=model_mode,
        folds=fold_metrics_list,
        ndcg_at_5=_summarize([r.ndcg_at_5 for r in all_results], [f.ndcg_at_5 for f in fold_metrics_list]),
        map=_summarize([r.average_precision for r in all_results], [f.map for f in fold_metrics_list]),
        normalized_precision_at_5=_summarize([r.normalized_precision_at_5 for r in all_results], [f.normalized_precision_at_5 for f in fold_metrics_list]),
        normalized_recall_at_5=_summarize([r.normalized_recall_at_5 for r in all_results], [f.normalized_recall_at_5 for f in fold_metrics_list]),
        precision_at_5=_summarize([r.precision_at_5 for r in all_results], [f.precision_at_5 for f in fold_metrics_list]),
        recall_at_5=_summarize([r.recall_at_5 for r in all_results], [f.recall_at_5 for f in fold_metrics_list]),
        ndcg_at_10=_summarize([r.ndcg_at_10 for r in all_results], [f.ndcg_at_10 for f in fold_metrics_list]),
        r_precision=_summarize([r.r_precision for r in all_results], [f.r_precision for f in fold_metrics_list]),
        recall_at_20=_summarize([r.recall_at_20 for r in all_results], [f.recall_at_20 for f in fold_metrics_list]),
        recall_at_50=_summarize([r.recall_at_50 for r in all_results], [f.recall_at_50 for f in fold_metrics_list]),
        recall_at_100=_summarize([r.recall_at_100 for r in all_results], [f.recall_at_100 for f in fold_metrics_list]),
        unthresholded_ndcg_at_5=_summarize([r.unthresholded_ndcg_at_5 for r in all_results], [f.unthresholded_ndcg_at_5 for f in fold_metrics_list]),
        unthresholded_precision_at_5=_summarize([r.unthresholded_precision_at_5 for r in all_results], [f.unthresholded_precision_at_5 for f in fold_metrics_list]),
        unthresholded_recall_at_5=_summarize([r.unthresholded_recall_at_5 for r in all_results], [f.unthresholded_recall_at_5 for f in fold_metrics_list]),
        retrieval_mean_rank=_summarize(ret_mean_ranks, [f.retrieval_mean_rank for f in fold_metrics_list]),
        rerank_mean_rank=_summarize(rerank_mean_ranks, [f.rerank_mean_rank for f in fold_metrics_list]),
        score_mean_rank=_summarize(score_mean_ranks, [f.score_mean_rank for f in fold_metrics_list]),
        latency_ms=_summarize([r.latency_ms for r in all_results], [f.mean_latency_ms for f in fold_metrics_list]),
        mrr=_summarize([r.mrr for r in all_results], [f.mrr for f in fold_metrics_list]),
        hit_rate_at_5=_summarize([r.hit_rate_at_5 for r in all_results], [f.hit_rate_at_5 for f in fold_metrics_list]),
        funnel_summary={
            "total_corpus_relevant": sum(r.funnel.corpus_relevant_count for r in all_results if r.funnel),
            "retrieval_retained": sum(r.funnel.retrieval_retained_count for r in all_results if r.funnel),
            "retrieval_lost": sum(r.funnel.retrieval_lost_count for r in all_results if r.funnel),
            "retrieval_mean_rank": _safe_mean(ret_mean_ranks),
            "rerank_mean_rank": _safe_mean(rerank_mean_ranks),
            "score_mean_rank": _safe_mean(score_mean_ranks),
            "threshold_retained": sum(r.funnel.threshold_retained_count for r in all_results if r.funnel),
            "threshold_lost": sum(r.funnel.threshold_lost_count for r in all_results if r.funnel),
            "final_top5_retained": sum(r.funnel.final_top5_retained_count for r in all_results if r.funnel),
            "final_top5_lost": sum(r.funnel.final_top5_lost_count for r in all_results if r.funnel),
        },
    )


def run_cross_validation(
    candidate_pool: str = "golden",  # 'golden' (30) or 'dev' (30 golden + 48 synthetic dev = 78)
    n_folds: int = 5,
    min_match: int = 50,
    retrieval_k: int = 100,
    seed: int = 42,
    output_path: Optional[Path] = None,
) -> CrossValidationComparison:
    """
    Executes candidate-level K-Fold cross-validation with real fold retraining
    and fixed model baseline comparison.
    """
    evaluator = UnifiedCandidateEvaluator(min_match=min_match)
    trainer = CrossValidationTrainer(evaluator)

    splits = evaluator.synthetic_loader.load_splits()
    golden_cands = sorted(evaluator.golden_resumes.keys())

    if candidate_pool == "golden":
        golden_splits = evaluator.golden_loader.load_splits()
        if golden_splits:
            candidate_ids = sorted([cid for cid, s in golden_splits.items() if s in ("train", "validation")])
        else:
            candidate_ids = golden_cands
    elif candidate_pool == "golden_all":
        candidate_ids = golden_cands
    elif candidate_pool == "golden_test":
        golden_splits = evaluator.golden_loader.load_splits()
        candidate_ids = sorted([cid for cid, s in golden_splits.items() if s == "test"])
    elif candidate_pool == "dev":
        synth_cands = [c for c, s in splits.items() if s in ("train", "validation")]
        candidate_ids = sorted(golden_cands + synth_cands)
    elif candidate_pool == "synthetic_dev":
        candidate_ids = [c for c, s in splits.items() if s in ("train", "validation")]
    elif candidate_pool == "all":
        synth_cands = sorted(evaluator.synthetic_resumes.keys())
        candidate_ids = sorted(golden_cands + synth_cands)
    else:
        raise ValueError(f"Unknown candidate_pool: {candidate_pool}")

    folds_cands = partition_candidates_kfold(candidate_ids, n_folds=n_folds, seed=seed)

    retrained_all_results: List[RecommendationCaseResult] = []
    fixed_all_results: List[RecommendationCaseResult] = []

    retrained_fold_metrics: List[FoldMetrics] = []
    fixed_fold_metrics: List[FoldMetrics] = []

    for fold_idx in range(n_folds):
        test_cands = folds_cands[fold_idx]
        val_fold_idx = (fold_idx + 1) % n_folds
        val_cands = folds_cands[val_fold_idx]
        train_cands = [
            cid for f_idx, fold in enumerate(folds_cands)
            if f_idx not in (fold_idx, val_fold_idx)
            for cid in fold
        ]
        if not train_cands:
            train_cands = val_cands

        # Retrain LightGBM LambdaMART on train folds with val early stopping
        fold_ranker = trainer.train_fold(train_cands, val_cands, seed=seed + fold_idx)

        # Evaluate test fold candidates
        f_retrained_results: List[RecommendationCaseResult] = []
        f_fixed_results: List[RecommendationCaseResult] = []

        for cid in test_cands:
            res_retrained = evaluator.evaluate_candidate(
                cid,
                retrieval_k=retrieval_k,
                custom_ranker=fold_ranker,
            )
            res_fixed = evaluator.evaluate_candidate(
                cid,
                retrieval_k=retrieval_k,
                custom_ranker=None,
            )
            f_retrained_results.append(res_retrained)
            f_fixed_results.append(res_fixed)
            retrained_all_results.append(res_retrained)
            fixed_all_results.append(res_fixed)

        def _make_fold_metrics(results: List[RecommendationCaseResult]) -> FoldMetrics:
            return FoldMetrics(
                fold_index=fold_idx + 1,
                num_candidates=len(results),
                candidate_ids=test_cands,
                ndcg_at_5=_safe_mean([r.ndcg_at_5 for r in results]),
                map=_safe_mean([r.average_precision for r in results]),
                normalized_precision_at_5=_safe_mean([r.normalized_precision_at_5 for r in results]),
                normalized_recall_at_5=_safe_mean([r.normalized_recall_at_5 for r in results]),
                precision_at_5=_safe_mean([r.precision_at_5 for r in results]),
                recall_at_5=_safe_mean([r.recall_at_5 for r in results]),
                ndcg_at_10=_safe_mean([r.ndcg_at_10 for r in results]),
                r_precision=_safe_mean([r.r_precision for r in results]),
                recall_at_20=_safe_mean([r.recall_at_20 for r in results]),
                recall_at_50=_safe_mean([r.recall_at_50 for r in results]),
                recall_at_100=_safe_mean([r.recall_at_100 for r in results]),
                unthresholded_ndcg_at_5=_safe_mean([r.unthresholded_ndcg_at_5 for r in results]),
                unthresholded_precision_at_5=_safe_mean([r.unthresholded_precision_at_5 for r in results]),
                unthresholded_recall_at_5=_safe_mean([r.unthresholded_recall_at_5 for r in results]),
                retrieval_mean_rank=_safe_mean([r.funnel.retrieval_mean_rank_relevant for r in results if r.funnel]),
                rerank_mean_rank=_safe_mean([r.funnel.rerank_mean_rank_relevant for r in results if r.funnel]),
                score_mean_rank=_safe_mean([r.funnel.score_mean_rank_relevant for r in results if r.funnel]),
                total_lost_at_retrieval=sum(r.funnel.retrieval_lost_count for r in results if r.funnel),
                total_lost_at_threshold=sum(r.funnel.threshold_lost_count for r in results if r.funnel),
                mean_latency_ms=_safe_mean([r.latency_ms for r in results]),
                mrr=_safe_mean([r.mrr for r in results]),
                hit_rate_at_5=_safe_mean([r.hit_rate_at_5 for r in results]),
            )

        retrained_fold_metrics.append(_make_fold_metrics(f_retrained_results))
        fixed_fold_metrics.append(_make_fold_metrics(f_fixed_results))

    summary_retrained = _build_summary(
        retrained_all_results,
        retrained_fold_metrics,
        n_folds=n_folds,
        candidate_pool=candidate_pool,
        model_mode="retrained_cv",
        seed=seed,
    )

    summary_fixed = _build_summary(
        fixed_all_results,
        fixed_fold_metrics,
        n_folds=n_folds,
        candidate_pool=candidate_pool,
        model_mode="fixed_baseline",
        seed=seed,
    )

    comparison = CrossValidationComparison(
        candidate_pool=candidate_pool,
        n_folds=n_folds,
        retrained=summary_retrained,
        fixed=summary_fixed,
    )

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(asdict(comparison), f, indent=2)

    return comparison


def evaluate_test_split(
    evaluator: Optional[UnifiedCandidateEvaluator] = None,
    min_match: int = 50,
    retrieval_k: int = 100,
    custom_ranker: Optional[Any] = None,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Evaluates strictly the 24 held-out test candidates on Golden v2.
    These candidates are strictly reserved and never touched during training or CV tuning.
    """
    if evaluator is None:
        evaluator = UnifiedCandidateEvaluator(min_match=min_match)

    golden_splits = evaluator.golden_loader.load_splits()
    test_cands = sorted([cid for cid, s in golden_splits.items() if s == "test"])

    results: List[RecommendationCaseResult] = []
    for cid in test_cands:
        res = evaluator.evaluate_candidate(
            cid,
            retrieval_k=retrieval_k,
            custom_ranker=custom_ranker,
        )
        results.append(res)

    def _summarize(values: List[float]) -> MetricSummary:
        mean_val = _safe_mean(values)
        std_val = _safe_std(values)
        ci = bootstrap_ci(values, n_bootstrap=10000, ci=0.95, seed=seed)
        return MetricSummary(
            mean=mean_val,
            std=std_val,
            ci_lower=ci["ci_lower"],
            ci_upper=ci["ci_upper"],
        )

    test_metrics = {
        "num_candidates": len(results),
        "candidate_ids": test_cands,
        "ndcg_at_5": _summarize([r.ndcg_at_5 for r in results]),
        "map": _summarize([r.average_precision for r in results]),
        "normalized_precision_at_5": _summarize([r.normalized_precision_at_5 for r in results]),
        "normalized_recall_at_5": _summarize([r.normalized_recall_at_5 for r in results]),
        "precision_at_5": _summarize([r.precision_at_5 for r in results]),
        "recall_at_5": _summarize([r.recall_at_5 for r in results]),
        "r_precision": _summarize([r.r_precision for r in results]),
        "results": results,
    }
    return test_metrics
