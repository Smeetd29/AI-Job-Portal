from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np

from eval.src.data_loader import GoldenDataLoader, GoldenJob, GoldenRecommendation, GoldenResume


def _deduplicate_preserving_order(items: List[str]) -> List[str]:
    """Deduplicates a list of item IDs while preserving ranked order."""
    seen = set()
    deduped = []
    for item in items:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def calculate_precision_at_k(retrieved_ids: List[str], relevant_ids: Set[str], k: int) -> float:
    """
    Precision@K = (number of unique relevant items in top K) / K.
    Standard TREC fixed-K denominator convention.
    """
    if k <= 0:
        return 0.0
    deduped = _deduplicate_preserving_order(retrieved_ids)
    top_k = deduped[:k]
    if not top_k:
        return 0.0
    hits = sum(1 for item_id in top_k if item_id in relevant_ids)
    return hits / float(k)


def calculate_max_possible_precision_at_k(n_relevant: int, k: int) -> float:
    """
    Theoretical maximum possible Precision@K given n_relevant items in the corpus:
    max_possible_P@K = min(K, n_relevant) / K.
    """
    if k <= 0:
        return 0.0
    return min(float(k), float(max(0, n_relevant))) / float(k)


def calculate_max_possible_recall_at_k(n_relevant: int, k: int) -> float:
    """
    Theoretical maximum possible Recall@K given n_relevant items in the corpus:
    max_possible_R@K = min(K, n_relevant) / n_relevant.
    Returns float('nan') when n_relevant <= 0.
    """
    if n_relevant <= 0:
        return float("nan")
    if k <= 0:
        return 0.0
    return min(float(k), float(n_relevant)) / float(n_relevant)


def calculate_normalized_precision_at_k(
    retrieved_ids: List[str],
    relevant_ids: Set[str],
    k: int,
) -> float:
    """
    Normalized Precision@K = actual P@K / max_possible P@K.
    Accounts for the ceiling effect where corpus contains fewer than K relevant items.
    """
    max_p = calculate_max_possible_precision_at_k(len(relevant_ids), k)
    if max_p <= 0.0:
        return 0.0
    p = calculate_precision_at_k(retrieved_ids, relevant_ids, k)
    return min(1.0, p / max_p)


def calculate_normalized_recall_at_k(
    retrieved_ids: List[str],
    relevant_ids: Set[str],
    k: int,
) -> float:
    """
    Normalized Recall@K = actual R@K / max_possible R@K.
    Accounts for the capacity ceiling of K when n_relevant > K.
    """
    max_r = calculate_max_possible_recall_at_k(len(relevant_ids), k)
    if math.isnan(max_r) or max_r <= 0.0:
        return float("nan")
    r = calculate_recall_at_k(retrieved_ids, relevant_ids, k)
    if math.isnan(r):
        return float("nan")
    return min(1.0, r / max_r)


def calculate_average_precision(
    retrieved_ids: List[str],
    relevant_ids: Set[str],
) -> float:
    """
    Average Precision (AP) for a single ranked list.
    AP = (1 / |relevant_ids|) * sum_{i=1}^N (P@i * I(doc_i in relevant_ids)).
    Returns float('nan') if relevant_ids is empty.
    """
    if not relevant_ids:
        return float("nan")
    deduped = _deduplicate_preserving_order(retrieved_ids)
    if not deduped:
        return 0.0
    hits = 0
    sum_precisions = 0.0
    for rank, item_id in enumerate(deduped, 1):
        if item_id in relevant_ids:
            hits += 1
            sum_precisions += hits / float(rank)
    return sum_precisions / float(len(relevant_ids))


def calculate_r_precision(
    retrieved_ids: List[str],
    relevant_ids: Set[str],
) -> float:
    """
    R-Precision = Precision at rank R, where R = len(relevant_ids).
    Returns float('nan') if relevant_ids is empty.
    """
    r = len(relevant_ids)
    if r <= 0:
        return float("nan")
    deduped = _deduplicate_preserving_order(retrieved_ids)
    top_r = deduped[:r]
    hits = sum(1 for item_id in top_r if item_id in relevant_ids)
    return hits / float(r)


def bootstrap_ci(
    values: List[float],
    n_bootstrap: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
) -> Dict[str, float]:
    """
    Computes non-parametric percentile bootstrap 95% confidence intervals.
    Returns dict with mean, std, ci_lower, and ci_upper.
    """
    valid = [v for v in values if not math.isnan(v)]
    if not valid:
        return {"mean": float("nan"), "std": float("nan"), "ci_lower": float("nan"), "ci_upper": float("nan")}
    arr = np.array(valid, dtype=np.float64)
    n = len(arr)
    if n == 1:
        return {"mean": float(arr[0]), "std": 0.0, "ci_lower": float(arr[0]), "ci_upper": float(arr[0])}
    rng = np.random.default_rng(seed)
    boot_indices = rng.integers(0, n, size=(n_bootstrap, n))
    boot_means = np.mean(arr[boot_indices], axis=1)
    alpha = (1.0 - ci) / 2.0
    ci_lower = float(np.percentile(boot_means, alpha * 100.0))
    ci_upper = float(np.percentile(boot_means, (1.0 - alpha) * 100.0))
    return {
        "mean": float(np.mean(arr)),
        "std": float(np.std(arr, ddof=1)) if n > 1 else 0.0,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
    }


def calculate_recall_at_k(retrieved_ids: List[str], relevant_ids: Set[str], k: int) -> float:
    """
    Recall@K = (number of unique relevant items in top K) / (total known relevant items in corpus).
    If total known relevant items in corpus is 0: returns float('nan').
    """
    if not relevant_ids:
        return float("nan")
    if k <= 0:
        return 0.0
    deduped = _deduplicate_preserving_order(retrieved_ids)
    top_k = deduped[:k]
    hits = sum(1 for item_id in top_k if item_id in relevant_ids)
    return hits / float(len(relevant_ids))


def calculate_hit_rate_at_k(retrieved_ids: List[str], relevant_ids: Set[str], k: int) -> float:
    """HitRate@K = 1.0 if at least one relevant item appears in top K, else 0.0."""
    if k <= 0:
        return 0.0
    deduped = _deduplicate_preserving_order(retrieved_ids)
    top_k = deduped[:k]
    return 1.0 if any(item_id in relevant_ids for item_id in top_k) else 0.0


def calculate_mrr(retrieved_ids: List[str], relevant_ids: Set[str]) -> float:
    """Mean Reciprocal Rank = 1 / rank of first relevant item (1-indexed)."""
    deduped = _deduplicate_preserving_order(retrieved_ids)
    for rank, item_id in enumerate(deduped, 1):
        if item_id in relevant_ids:
            return 1.0 / float(rank)
    return 0.0


def calculate_ndcg_at_k(
    retrieved_ids: List[str],
    graded_relevance: Dict[str, int],
    k: int,
) -> float:
    """
    nDCG@K using graded relevance with standard exponential gain:
    DCG@K = sum_{i=1}^K (2^{rel_i} - 1) / log2(i + 1)
    IDCG@K = ideal DCG obtained by sorting all known relevant grades in corpus descending.
    If IDCG == 0: returns float('nan') if corpus has no relevant items, else 0.0.
    """
    if k <= 0:
        return 0.0

    deduped = _deduplicate_preserving_order(retrieved_ids)
    top_k = deduped[:k]

    dcg = 0.0
    for i, item_id in enumerate(top_k, 1):
        rel = graded_relevance.get(item_id, 0)
        gain = (2.0 ** rel) - 1.0
        discount = math.log2(i + 1.0)
        dcg += gain / discount

    # Ideal DCG over the entire evaluation corpus for this query
    all_grades = sorted(graded_relevance.values(), reverse=True)[:k]
    idcg = 0.0
    for i, rel in enumerate(all_grades, 1):
        gain = (2.0 ** rel) - 1.0
        discount = math.log2(i + 1.0)
        idcg += gain / discount

    if idcg == 0.0:
        has_positive = any(v > 0 for v in graded_relevance.values())
        return 0.0 if has_positive else float("nan")
    return dcg / idcg


@dataclass
class QueryRetrievalResult:
    resume_id: str
    retrieved_job_ids: List[str]
    retrieved_scores: List[float]
    relevant_job_ids: List[str]
    graded_relevance: Dict[str, int]
    precision_at_3: float
    precision_at_5: float
    precision_at_10: float
    recall_at_3: float
    recall_at_5: float
    recall_at_10: float
    hit_rate_at_5: float
    mrr: float
    ndcg_at_5: float
    latency_ms: float
    error: Optional[str] = None
    n_relevant: int = 0
    max_possible_p5: float = 0.0
    max_possible_r5: float = 0.0
    normalized_precision_at_5: float = 0.0
    normalized_recall_at_5: float = 0.0
    recall_at_20: float = 0.0
    recall_at_50: float = 0.0
    recall_at_100: float = 0.0
    ndcg_at_10: float = 0.0
    average_precision: float = 0.0
    r_precision: float = 0.0


@dataclass
class RetrievalBenchmarkSummary:
    total_queries: int
    mean_precision_at_3: float
    mean_precision_at_5: float
    mean_precision_at_10: float
    mean_recall_at_3: float
    mean_recall_at_5: float
    mean_recall_at_10: float
    mean_hit_rate_at_5: float
    mean_mrr: float
    mean_ndcg_at_5: float
    mean_latency_ms: float
    failed_queries: List[str] = field(default_factory=list)
    mean_n_relevant: float = 0.0
    mean_max_possible_p5: float = 0.0
    mean_max_possible_r5: float = 0.0
    mean_normalized_precision_at_5: float = 0.0
    mean_normalized_recall_at_5: float = 0.0
    mean_recall_at_20: float = 0.0
    mean_recall_at_50: float = 0.0
    mean_recall_at_100: float = 0.0
    mean_ndcg_at_10: float = 0.0
    mean_average_precision: float = 0.0
    mean_r_precision: float = 0.0
    confidence_intervals: Dict[str, Dict[str, float]] = field(default_factory=dict)


class RetrievalEvaluator:
    """Evaluates CareerConnect's FAISS dense retriever against complete golden relevance judgments."""

    def __init__(
        self,
        loader: Optional[GoldenDataLoader] = None,
        embedding_model: Optional[Any] = None,
        retriever_instance: Optional[Any] = None,
    ):
        self.loader = loader or GoldenDataLoader()
        self.jobs = self.loader.load_jobs()
        self.resumes = self.loader.load_resumes()
        self.recommendations = self.loader.load_recommendations()

        # Build lookup tables
        self.relevance_by_resume: Dict[str, Dict[str, int]] = {}
        for rec in self.recommendations:
            if rec.resume_id not in self.relevance_by_resume:
                self.relevance_by_resume[rec.resume_id] = {}
            self.relevance_by_resume[rec.resume_id][rec.job_id] = rec.relevance

        self._embedding_model = embedding_model
        self._retriever = retriever_instance
        self._indexed = False

    def _ensure_pipeline(self) -> None:
        if self._indexed:
            return

        if self._embedding_model is None:
            from application.ai.matching import SentenceTransformerEmbedding
            self._embedding_model = SentenceTransformerEmbedding(lazy_load=False)

        if self._retriever is None:
            from application.ai.matching import FaissRetriever
            self._retriever = FaissRetriever(embedding_dim=self._embedding_model.embedding_dim)

            # Build index from golden jobs
            job_ids = list(self.jobs.keys())
            job_texts = [
                f"{job.title}. {job.category}. {job.description[:600]}"
                for job in self.jobs.values()
            ]
            vectors = self._embedding_model.encode(job_texts)
            # Map string job IDs to integer internal indices
            self._int_to_str_id = {idx: jid for idx, jid in enumerate(job_ids)}
            self._str_to_int_id = {jid: idx for idx, jid in enumerate(job_ids)}
            int_ids = list(range(len(job_ids)))
            self._retriever.add_documents(int_ids, vectors)

        self._indexed = True

    def evaluate_query(
        self,
        resume_id: str,
        query_text: Optional[str] = None,
        top_k: int = 10,
    ) -> QueryRetrievalResult:
        self._ensure_pipeline()
        resume = self.resumes.get(resume_id)
        if not resume:
            raise ValueError(f"Resume {resume_id} not found in golden resumes.")

        # Zero gold-label leak assertion: Candidate query representation must use parsed text only
        assert hasattr(resume, "resume_text") and resume.resume_text, f"Candidate {resume_id} missing resume_text."

        if query_text is None:
            # Query built strictly from parsed resume text, NOT golden resume.skills or preferred_roles
            from application.ai.pipeline import MatchingPipeline
            pipeline = MatchingPipeline.get_default()
            cleaned = pipeline.cleaner(resume.resume_text)
            doc = pipeline.resume_parser.parse(cleaned, raw_text=resume.resume_text)
            ex = pipeline.skill_extractor.extract
            norm = pipeline.normalizer.normalize_list
            parsed_skills = norm(ex(doc.skills_section or cleaned))
            parsed_sen = pipeline.seniority_extractor.extract(cleaned)
            sen_str = parsed_sen.title() if parsed_sen else "Mid"
            skills_str = ", ".join(parsed_skills[:8])
            query_text = f"{sen_str}. {skills_str}. {cleaned[:400]}"

        t0 = time.perf_counter()
        query_vec = self._embedding_model.encode([query_text])[0]
        raw_results = self._retriever.search(query_vec, top_k=top_k)
        latency_ms = (time.perf_counter() - t0) * 1000.0

        retrieved_job_ids = [self._int_to_str_id.get(r.document_id, str(r.document_id)) for r in raw_results]
        retrieved_scores = [r.score for r in raw_results]

        graded = self.relevance_by_resume.get(resume_id, {})
        relevant_ids = {jid for jid, grade in graded.items() if grade >= 2}
        n_rel = len(relevant_ids)

        p3 = calculate_precision_at_k(retrieved_job_ids, relevant_ids, 3)
        p5 = calculate_precision_at_k(retrieved_job_ids, relevant_ids, 5)
        p10 = calculate_precision_at_k(retrieved_job_ids, relevant_ids, 10)

        r3 = calculate_recall_at_k(retrieved_job_ids, relevant_ids, 3)
        r5 = calculate_recall_at_k(retrieved_job_ids, relevant_ids, 5)
        r10 = calculate_recall_at_k(retrieved_job_ids, relevant_ids, 10)
        r20 = calculate_recall_at_k(retrieved_job_ids, relevant_ids, 20)
        r50 = calculate_recall_at_k(retrieved_job_ids, relevant_ids, 50)
        r100 = calculate_recall_at_k(retrieved_job_ids, relevant_ids, 100)

        max_p5 = calculate_max_possible_precision_at_k(n_rel, 5)
        max_r5 = calculate_max_possible_recall_at_k(n_rel, 5)
        norm_p5 = calculate_normalized_precision_at_k(retrieved_job_ids, relevant_ids, 5)
        norm_r5 = calculate_normalized_recall_at_k(retrieved_job_ids, relevant_ids, 5)

        hr5 = calculate_hit_rate_at_k(retrieved_job_ids, relevant_ids, 5)
        mrr = calculate_mrr(retrieved_job_ids, relevant_ids)
        ndcg5 = calculate_ndcg_at_k(retrieved_job_ids, graded, 5)
        ndcg10 = calculate_ndcg_at_k(retrieved_job_ids, graded, 10)
        ap = calculate_average_precision(retrieved_job_ids, relevant_ids)
        r_prec = calculate_r_precision(retrieved_job_ids, relevant_ids)

        return QueryRetrievalResult(
            resume_id=resume_id,
            retrieved_job_ids=retrieved_job_ids,
            retrieved_scores=retrieved_scores,
            relevant_job_ids=list(relevant_ids),
            graded_relevance=graded,
            precision_at_3=p3,
            precision_at_5=p5,
            precision_at_10=p10,
            recall_at_3=r3,
            recall_at_5=r5,
            recall_at_10=r10,
            hit_rate_at_5=hr5,
            mrr=mrr,
            ndcg_at_5=ndcg5,
            latency_ms=latency_ms,
            n_relevant=n_rel,
            max_possible_p5=max_p5,
            max_possible_r5=max_r5,
            normalized_precision_at_5=norm_p5,
            normalized_recall_at_5=norm_r5,
            recall_at_20=r20,
            recall_at_50=r50,
            recall_at_100=r100,
            ndcg_at_10=ndcg10,
            average_precision=ap,
            r_precision=r_prec,
        )

    def evaluate_all(
        self,
        output_artifact_path: Optional[Path] = None,
        top_k: int = 10,
    ) -> Tuple[RetrievalBenchmarkSummary, List[QueryRetrievalResult]]:
        self._ensure_pipeline()
        results: List[QueryRetrievalResult] = []
        failed_queries: List[str] = []

        for resume_id in sorted(self.resumes.keys()):
            if resume_id not in self.relevance_by_resume:
                continue
            try:
                res = self.evaluate_query(resume_id=resume_id, top_k=top_k)
                results.append(res)
            except Exception as exc:
                failed_queries.append(resume_id)
                results.append(QueryRetrievalResult(
                    resume_id=resume_id,
                    retrieved_job_ids=[],
                    retrieved_scores=[],
                    relevant_job_ids=[],
                    graded_relevance={},
                    precision_at_3=0.0,
                    precision_at_5=0.0,
                    precision_at_10=0.0,
                    recall_at_3=0.0,
                    recall_at_5=0.0,
                    recall_at_10=0.0,
                    hit_rate_at_5=0.0,
                    mrr=0.0,
                    ndcg_at_5=0.0,
                    latency_ms=0.0,
                    error=str(exc),
                ))

        # Filter out NaN for queries with no relevant items
        def safe_mean(values: List[float]) -> float:
            valid = [v for v in values if not math.isnan(v)]
            return float(np.mean(valid)) if valid else 0.0

        ci_metrics = {
            "precision_at_5": bootstrap_ci([r.precision_at_5 for r in results]),
            "normalized_precision_at_5": bootstrap_ci([r.normalized_precision_at_5 for r in results]),
            "recall_at_5": bootstrap_ci([r.recall_at_5 for r in results]),
            "normalized_recall_at_5": bootstrap_ci([r.normalized_recall_at_5 for r in results]),
            "ndcg_at_5": bootstrap_ci([r.ndcg_at_5 for r in results]),
            "ndcg_at_10": bootstrap_ci([r.ndcg_at_10 for r in results]),
            "map": bootstrap_ci([r.average_precision for r in results]),
            "r_precision": bootstrap_ci([r.r_precision for r in results]),
            "mrr": bootstrap_ci([r.mrr for r in results]),
            "hit_rate_at_5": bootstrap_ci([r.hit_rate_at_5 for r in results]),
        }

        summary = RetrievalBenchmarkSummary(
            total_queries=len(results),
            mean_precision_at_3=safe_mean([r.precision_at_3 for r in results]),
            mean_precision_at_5=safe_mean([r.precision_at_5 for r in results]),
            mean_precision_at_10=safe_mean([r.precision_at_10 for r in results]),
            mean_recall_at_3=safe_mean([r.recall_at_3 for r in results]),
            mean_recall_at_5=safe_mean([r.recall_at_5 for r in results]),
            mean_recall_at_10=safe_mean([r.recall_at_10 for r in results]),
            mean_hit_rate_at_5=safe_mean([r.hit_rate_at_5 for r in results]),
            mean_mrr=safe_mean([r.mrr for r in results]),
            mean_ndcg_at_5=safe_mean([r.ndcg_at_5 for r in results]),
            mean_latency_ms=safe_mean([r.latency_ms for r in results]),
            failed_queries=failed_queries,
            mean_n_relevant=safe_mean([float(r.n_relevant) for r in results]),
            mean_max_possible_p5=safe_mean([r.max_possible_p5 for r in results]),
            mean_max_possible_r5=safe_mean([r.max_possible_r5 for r in results]),
            mean_normalized_precision_at_5=safe_mean([r.normalized_precision_at_5 for r in results]),
            mean_normalized_recall_at_5=safe_mean([r.normalized_recall_at_5 for r in results]),
            mean_recall_at_20=safe_mean([r.recall_at_20 for r in results]),
            mean_recall_at_50=safe_mean([r.recall_at_50 for r in results]),
            mean_recall_at_100=safe_mean([r.recall_at_100 for r in results]),
            mean_ndcg_at_10=safe_mean([r.ndcg_at_10 for r in results]),
            mean_average_precision=safe_mean([r.average_precision for r in results]),
            mean_r_precision=safe_mean([r.r_precision for r in results]),
            confidence_intervals=ci_metrics,
        )

        if output_artifact_path:
            output_artifact_path.parent.mkdir(parents=True, exist_ok=True)
            with output_artifact_path.open("x", encoding="utf-8") as f:
                for r in results:
                    f.write(json.dumps(asdict(r)) + "\n")

        return summary, results
