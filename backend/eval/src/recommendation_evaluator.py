from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np

from eval.src.data_loader import GoldenDataLoader, GoldenJob, GoldenRecommendation, GoldenResume
from eval.src.retrieval_evaluator import (
    calculate_average_precision,
    calculate_hit_rate_at_k,
    calculate_max_possible_precision_at_k,
    calculate_max_possible_recall_at_k,
    calculate_mrr,
    calculate_ndcg_at_k,
    calculate_normalized_precision_at_k,
    calculate_normalized_recall_at_k,
    calculate_precision_at_k,
    calculate_r_precision,
    calculate_recall_at_k,
    bootstrap_ci,
    _deduplicate_preserving_order,
)


@dataclass
class FunnelLossReport:
    corpus_relevant_count: int
    retrieval_retained_count: int
    retrieval_lost_count: int
    retrieval_mean_rank_relevant: float
    rerank_retained_count: int
    rerank_mean_rank_relevant: float
    score_retained_count: int
    score_mean_rank_relevant: float
    threshold_retained_count: int
    threshold_lost_count: int
    final_top5_retained_count: int
    final_top5_lost_count: int


@dataclass
class RecommendationPipelineStages:
    raw_retrieved_ids: List[str]
    reranked_ids: List[str]
    scored_ids: List[str]
    filtered_ids: List[str]
    final_recommended_ids: List[str]
    final_scores: List[int]
    lost_relevant_at_retrieval: List[str]
    lost_relevant_at_ranking: List[str]
    lost_relevant_at_threshold: List[str]
    unthresholded_recommended_ids: List[str] = field(default_factory=list)
    funnel: Optional[FunnelLossReport] = None


@dataclass
class RankingStageMetrics:
    precision_at_5: float
    recall_at_5: float
    hit_rate_at_5: float
    mrr: float
    ndcg_at_5: float
    ndcg_at_10: float = 0.0
    map: float = 0.0
    r_precision: float = 0.0
    recall_at_20: float = 0.0
    recall_at_50: float = 0.0
    recall_at_100: float = 0.0
    normalized_precision_at_5: float = 0.0
    normalized_recall_at_5: float = 0.0


@dataclass
class RecommendationCaseResult:
    resume_id: str
    recommended_job_ids: List[str]
    match_scores: List[int]
    relevant_job_ids: List[str]
    graded_relevance: Dict[str, int]
    precision_at_3: float
    precision_at_5: float
    recall_at_3: float
    recall_at_5: float
    hit_rate_at_5: float
    mrr: float
    ndcg_at_5: float
    duplicate_count: int
    category_coverage: float
    skill_compatibility_score: float
    seniority_compatibility_score: float
    latency_ms: float
    stages: RecommendationPipelineStages
    matched_skills_sample: List[str] = field(default_factory=list)
    skill_gaps_sample: List[str] = field(default_factory=list)
    n_relevant: int = 0
    max_possible_precision_at_5: float = 0.0
    max_possible_recall_at_5: float = 0.0
    normalized_precision_at_5: float = 0.0
    normalized_recall_at_5: float = 0.0
    recall_at_20: float = 0.0
    recall_at_50: float = 0.0
    recall_at_100: float = 0.0
    ndcg_at_10: float = 0.0
    average_precision: float = 0.0
    r_precision: float = 0.0
    unthresholded_recommended_ids: List[str] = field(default_factory=list)
    unthresholded_precision_at_5: float = 0.0
    unthresholded_recall_at_5: float = 0.0
    unthresholded_normalized_precision_at_5: float = 0.0
    unthresholded_normalized_recall_at_5: float = 0.0
    unthresholded_ndcg_at_5: float = 0.0
    unthresholded_mrr: float = 0.0
    unthresholded_hit_rate_at_5: float = 0.0
    funnel: Optional[FunnelLossReport] = None


@dataclass
class RecommendationBenchmarkSummary:
    total_candidates: int
    mean_precision_at_3: float
    mean_precision_at_5: float
    mean_recall_at_3: float
    mean_recall_at_5: float
    micro_precision_at_3: float = 0.0
    micro_precision_at_5: float = 0.0
    micro_recall_at_3: float = 0.0
    micro_recall_at_5: float = 0.0
    mean_hit_rate_at_5: float = 1.0
    mean_mrr: float = 1.0
    mean_ndcg_at_5: float = 0.0
    duplicate_rate: float = 0.0
    mean_category_coverage: float = 0.0
    corpus_category_coverage: float = 1.0
    corpus_job_coverage: float = 0.0
    mean_skill_compatibility: float = 0.0
    mean_seniority_compatibility: float = 0.0
    mean_latency_ms: float = 0.0
    total_lost_at_retrieval: int = 0
    total_lost_at_threshold: int = 0
    failed_candidates: List[str] = field(default_factory=list)
    stage_metrics: Dict[str, RankingStageMetrics] = field(default_factory=dict)
    mean_n_relevant: float = 0.0
    mean_max_possible_precision_at_5: float = 0.0
    mean_max_possible_recall_at_5: float = 0.0
    mean_normalized_precision_at_5: float = 0.0
    mean_normalized_recall_at_5: float = 0.0
    mean_recall_at_20: float = 0.0
    mean_recall_at_50: float = 0.0
    mean_recall_at_100: float = 0.0
    mean_ndcg_at_10: float = 0.0
    map: float = 0.0
    mean_r_precision: float = 0.0
    unthresholded_mean_precision_at_5: float = 0.0
    unthresholded_mean_recall_at_5: float = 0.0
    unthresholded_mean_normalized_precision_at_5: float = 0.0
    unthresholded_mean_normalized_recall_at_5: float = 0.0
    unthresholded_mean_ndcg_at_5: float = 0.0
    unthresholded_mean_mrr: float = 0.0
    unthresholded_mean_hit_rate_at_5: float = 0.0
    threshold_cost_precision_delta: float = 0.0
    threshold_cost_recall_delta: float = 0.0
    threshold_cost_ndcg_delta: float = 0.0
    funnel_summary: Dict[str, Any] = field(default_factory=dict)
    confidence_intervals: Dict[str, Dict[str, float]] = field(default_factory=dict)


class RecommendationEvaluator:
    """
    Evaluates CareerConnect's end-to-end Job Recommendation workflow across:
    Raw Retrieval -> Cross-Encoder Reranking -> 10-Feature Scoring -> Eligibility/Threshold Filtering -> Explanation.
    """

    def __init__(
        self,
        loader: Optional[GoldenDataLoader] = None,
        pipeline_instance: Optional[Any] = None,
        min_match: int = 50,
    ):
        self.loader = loader or GoldenDataLoader()
        self.jobs = self.loader.load_jobs()
        self.resumes = self.loader.load_resumes()
        self.recommendations = self.loader.load_recommendations()
        self.min_match = min_match

        # Map relevance judgments by resume_id
        self.relevance_by_resume: Dict[str, Dict[str, int]] = {}
        for rec in self.recommendations:
            if rec.resume_id not in self.relevance_by_resume:
                self.relevance_by_resume[rec.resume_id] = {}
            self.relevance_by_resume[rec.resume_id][rec.job_id] = rec.relevance

        self.pipeline = pipeline_instance
        self._retriever_indexed = False
        self._job_embeddings_cache: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}

    def _ensure_pipeline(self) -> None:
        if self.pipeline is None:
            from application.ai.pipeline import MatchingPipeline
            self.pipeline = MatchingPipeline.get_default()

        if not self._retriever_indexed:
            from application.ai.matching import HybridRetriever, BM25_AVAILABLE
            self._faiss = HybridRetriever(
                embedding_dim=self.pipeline.embedding.embedding_dim,
                use_bm25=BM25_AVAILABLE,
            )
            self._job_keys = list(self.jobs.keys())
            job_texts = [
                f"{job.title}. {job.category}. {job.description[:600]}"
                for job in self.jobs.values()
            ]
            vectors = self.pipeline.embedding.encode(job_texts)
            self._int_to_jid = {i: jid for i, jid in enumerate(self._job_keys)}
            self._jid_to_int = {jid: i for i, jid in enumerate(self._job_keys)}
            # Pass integer IDs (0..N-1) — same as before; HybridRetriever uses same id_map convention
            self._faiss.add_documents(
                list(range(len(self._job_keys))),
                vectors,
                texts=job_texts,
            )
            self._retriever_indexed = True

    def evaluate_candidate(
        self,
        resume_id: str,
        retrieval_k: int = 100,
        custom_ranker: Optional[Any] = None,
    ) -> RecommendationCaseResult:
        if custom_ranker is not None and hasattr(custom_ranker, "metadata"):
            train_cands = set(custom_ranker.metadata.get("train_candidates", []))
            if resume_id in train_cands:
                raise AssertionError(
                    f"LEAKAGE AUDIT FAILURE: Evaluated candidate '{resume_id}' was present in the ranker's training set!"
                )
        self._ensure_pipeline()
        resume = self.resumes.get(resume_id)
        if not resume:
            raise ValueError(f"Resume {resume_id} not found.")

        graded = self.relevance_by_resume.get(resume_id, {})
        relevant_ids = {jid for jid, grade in graded.items() if grade >= 2}

        t0 = time.perf_counter()

        # Parse candidate using production methods
        cleaned_resume = self.pipeline.cleaner(resume.resume_text)
        resume_doc = self.pipeline.resume_parser.parse(cleaned_resume, raw_text=resume.resume_text)

        norm = self.pipeline.normalizer.normalize_list
        ex = self.pipeline.skill_extractor.extract

        core = norm(ex(resume_doc.skills_section or cleaned_resume))
        proj = norm(ex(resume_doc.projects_section or ""))
        resume_doc.skill_candidates = core + [s for s in proj if s.lower() not in {c.lower() for c in core}] or norm(ex(cleaned_resume))
        resume_doc.years_experience = self.pipeline.experience_extractor.extract(
            resume_doc.experience_section or cleaned_resume
        )
        resume_doc.degree_level = self.pipeline.education_extractor.extract(
            resume_doc.education_section or cleaned_resume
        )
        resume_doc.seniority_label = self.pipeline.seniority_extractor.extract(
            cleaned_resume,
            years_experience=resume_doc.years_experience,
            degree_level=resume_doc.degree_level,
        )

        # Zero gold-label leak assertion: Candidate query representation must use parsed text only
        assert hasattr(resume, "resume_text") and resume.resume_text, f"Candidate {resume_id} missing resume_text."
        cand_seniority_str = resume_doc.seniority_label.title() if resume_doc.seniority_label else "Mid"
        cand_skills_str = ", ".join(resume_doc.skill_candidates[:8])
        role_text = f"{cand_seniority_str}. {cand_skills_str}. {cleaned_resume[:400]}"
        query_vec = self.pipeline.embedding.encode([role_text])[0]

        # STAGE 1: Dense Retrieval over candidate pool
        raw_retrieved = self._faiss.search(query_vec, top_k=min(retrieval_k, len(self._job_keys)), query_text=role_text)
        raw_retrieved_ids = [self._int_to_jid[r.document_id] for r in raw_retrieved]

        # Identify relevant items lost at Stage 1
        lost_at_retrieval = [jid for jid in relevant_ids if jid not in raw_retrieved_ids]

        # Prepare retrieved jobs for neural scoring
        candidate_jobs = [self.jobs[jid] for jid in raw_retrieved_ids]
        prepared_jobs = []
        for job in candidate_jobs:
            c_job = self.pipeline.cleaner(job.description)
            j_doc = self.pipeline.job_parser.parse(clean_text=c_job, title=job.title, raw_text=job.description)
            req_skills = getattr(job, "required_skills", None)
            if not req_skills:
                req_skills = ex(j_doc.required_skills_section or j_doc.qualifications_section or c_job)
            j_doc.required_skill_candidates = norm(req_skills or [])
            pref_skills = getattr(job, "preferred_skills", None)
            if not pref_skills:
                pref_skills = ex(j_doc.preferred_skills_section or "") if j_doc.preferred_skills_section else []
            j_doc.preferred_skill_candidates = norm(pref_skills or [])
            j_doc.required_years = self.pipeline.experience_extractor.extract(c_job)
            j_doc.required_degree_level = self.pipeline.education_extractor.extract(c_job)
            j_doc.seniority_label = self.pipeline.seniority_extractor.extract(
                f"{job.title}\n{c_job[:400]}",
                years_experience=j_doc.required_years,
                degree_level=j_doc.required_degree_level,
            )
            j_text = f"{job.title}. {', '.join(j_doc.required_skill_candidates)}. {c_job[:600]}"
            prepared_jobs.append((job, c_job, j_doc, j_text))

        # STAGE 2: Cross-Encoder Reranking
        r_skills = ", ".join(resume_doc.skill_candidates[:12])
        r_sen = resume_doc.seniority_label.title() if resume_doc.seniority_label else "Mid"
        r_exp = f"{resume_doc.years_experience:.0f} yrs" if resume_doc.years_experience else "1+ yrs"
        cand_text = f"Candidate Seniority: {r_sen}. Experience: {r_exp}. Skills: {r_skills}. {cleaned_resume[:400]}"
        ce_pairs = []
        for job, c_job, j_doc, _ in prepared_jobs:
            req_skills = ", ".join(j_doc.required_skill_candidates[:10])
            j_sen = j_doc.seniority_label.title() if j_doc.seniority_label else "Any"
            j_exp = f"{j_doc.required_years:.0f} yrs" if j_doc.required_years else "None"
            job_text = f"Role: {job.title}. Level: {j_sen}. Required Exp: {j_exp}. Skills: {req_skills}. {c_job[:400]}"
            ce_pairs.append((job_text, cand_text))
        cross_encoder_scores = self.pipeline.reranker.score_pairs(ce_pairs)

        # Pair up and rank by CE score for stage tracking
        ce_ranked = sorted(
            zip(raw_retrieved_ids, cross_encoder_scores),
            key=lambda x: x[1],
            reverse=True,
        )
        reranked_ids = [item[0] for item in ce_ranked]

        # STAGE 3: Tabular Feature Extraction & Scoring
        emb_res = self.pipeline.embedding.embed_text(cleaned_resume[:1000])
        role_emb = self.pipeline.embedding.embed_text(role_text[:600])

        missing_jobs = [item for item in prepared_jobs if item[0].job_id not in self._job_embeddings_cache]
        if missing_jobs:
            texts_to_embed = []
            for item in missing_jobs:
                texts_to_embed.append(item[3])
                texts_to_embed.append(f"{item[0].title} {item[0].category}")
            batch_embs = self.pipeline.embedding.embed_batch(texts_to_embed)
            for idx, item in enumerate(missing_jobs):
                self._job_embeddings_cache[item[0].job_id] = (batch_embs[idx * 2], batch_embs[idx * 2 + 1])

        from application.ai.ranking import profile_coverage
        w_dict = {s.lower(): 1.0 for s in resume_doc.skill_candidates}

        scored_stage = []
        for index, (job, c_job, j_doc, j_text) in enumerate(prepared_jobs):
            j_emb, j_title_emb = self._job_embeddings_cache[job.job_id]
            features = self.pipeline.feature_extractor.extract(
                resume_doc=resume_doc,
                job_doc=j_doc,
                resume_embedding=emb_res,
                job_embedding=j_emb,
                resume_summary_embedding=role_emb,
                job_title_embedding=j_title_emb,
                cross_encoder_score=cross_encoder_scores[index],
            )
            cov = profile_coverage(w_dict, f"{job.title} {', '.join(j_doc.required_skill_candidates)} {c_job}")
            ranker = custom_ranker or self.pipeline.ranker
            raw_ranker_score = ranker.score(features)
            final_match_score = max(0, min(100, int(round(raw_ranker_score))))
            scored_stage.append((job.job_id, final_match_score, job, j_doc))

        # Sort descending by match score
        scored_stage.sort(key=lambda x: x[1], reverse=True)
        scored_ids = [item[0] for item in scored_stage]

        # STAGE 4: Threshold Filtering with Top-5 Fallback
        filtered_stage = [item for item in scored_stage if item[1] >= self.min_match]
        if len(filtered_stage) < 5 and scored_stage:
            filtered_stage = scored_stage[:5]
        filtered_ids = [item[0] for item in filtered_stage]

        lost_at_threshold = [
            item[0] for item in scored_stage
            if item[0] in relevant_ids and item[1] < self.min_match and item[0] not in filtered_ids
        ]
        lost_at_ranking = [
            jid for jid in relevant_ids
            if jid in raw_retrieved_ids and jid not in filtered_ids and jid not in lost_at_threshold
        ]

        # STAGE 5: Final Recommendations (Top 5)
        final_top5 = filtered_stage[:5]
        rec_ids = [item[0] for item in final_top5]
        final_scores = [item[1] for item in final_top5]

        # Unthresholded comparison (Top 5 directly from scoring without threshold cut)
        unthresholded_top5 = scored_stage[:5]
        unthresh_rec_ids = [item[0] for item in unthresholded_top5]

        latency_ms = (time.perf_counter() - t0) * 1000.0

        # Deterministic Ranking & Relevance Metrics (Thresholded)
        p3 = calculate_precision_at_k(rec_ids, relevant_ids, 3)
        p5 = calculate_precision_at_k(rec_ids, relevant_ids, 5)
        r3 = calculate_recall_at_k(rec_ids, relevant_ids, 3)
        r5 = calculate_recall_at_k(rec_ids, relevant_ids, 5)
        hr5 = calculate_hit_rate_at_k(rec_ids, relevant_ids, 5)
        mrr = calculate_mrr(rec_ids, relevant_ids)
        ndcg5 = calculate_ndcg_at_k(rec_ids, graded, 5)

        # Theoretical Ceilings & Normalized Metrics
        n_rel = len(relevant_ids)
        max_p5 = calculate_max_possible_precision_at_k(n_rel, 5)
        max_r5 = calculate_max_possible_recall_at_k(n_rel, 5)
        norm_p5 = calculate_normalized_precision_at_k(rec_ids, relevant_ids, 5)
        norm_r5 = calculate_normalized_recall_at_k(rec_ids, relevant_ids, 5)

        # Extended metrics (nDCG@10, MAP, R-Precision, Recall@20, Recall@50)
        ndcg10 = calculate_ndcg_at_k(scored_ids[:10], graded, 10)
        ap = calculate_average_precision(scored_ids, relevant_ids)
        r_prec = calculate_r_precision(scored_ids, relevant_ids)
        r20 = calculate_recall_at_k(raw_retrieved_ids, relevant_ids, 20)
        r50 = calculate_recall_at_k(raw_retrieved_ids, relevant_ids, 50)
        r100 = calculate_recall_at_k(raw_retrieved_ids, relevant_ids, 100)

        # Unthresholded metrics for cost-of-threshold transparency
        unthresh_p5 = calculate_precision_at_k(unthresh_rec_ids, relevant_ids, 5)
        unthresh_r5 = calculate_recall_at_k(unthresh_rec_ids, relevant_ids, 5)
        unthresh_norm_p5 = calculate_normalized_precision_at_k(unthresh_rec_ids, relevant_ids, 5)
        unthresh_norm_r5 = calculate_normalized_recall_at_k(unthresh_rec_ids, relevant_ids, 5)
        unthresh_ndcg5 = calculate_ndcg_at_k(unthresh_rec_ids, graded, 5)
        unthresh_mrr = calculate_mrr(unthresh_rec_ids, relevant_ids)
        unthresh_hr5 = calculate_hit_rate_at_k(unthresh_rec_ids, relevant_ids, 5)

        # Stage Progression: Mean rank of relevant jobs across stages (which reorder rather than discard)
        def _calc_mean_rank(ranked_list: List[str], rel_set: Set[str]) -> float:
            ranks = [rank for rank, jid in enumerate(ranked_list, 1) if jid in rel_set]
            return float(np.mean(ranks)) if ranks else 0.0

        ret_mean_rank = _calc_mean_rank(raw_retrieved_ids, relevant_ids)
        rerank_mean_rank = _calc_mean_rank(reranked_ids, relevant_ids)
        score_mean_rank = _calc_mean_rank(scored_ids, relevant_ids)

        # Per-Stage Filtering Loss (Retrieval truncation, Threshold cut, Top 5 truncation)
        retained_ret = [jid for jid in raw_retrieved_ids if jid in relevant_ids]
        lost_ret = [jid for jid in relevant_ids if jid not in raw_retrieved_ids]

        retained_thresh = [item[0] for item in filtered_stage if item[0] in relevant_ids]
        lost_thresh = [item[0] for item in scored_stage if item[0] in relevant_ids and item[1] < self.min_match and item[0] not in filtered_ids]

        retained_top5 = [jid for jid in rec_ids if jid in relevant_ids]
        lost_top5 = [jid for jid in retained_thresh if jid not in rec_ids]

        funnel_report = FunnelLossReport(
            corpus_relevant_count=n_rel,
            retrieval_retained_count=len(retained_ret),
            retrieval_lost_count=len(lost_ret),
            retrieval_mean_rank_relevant=ret_mean_rank,
            rerank_retained_count=len(retained_ret),
            rerank_mean_rank_relevant=rerank_mean_rank,
            score_retained_count=len(retained_ret),
            score_mean_rank_relevant=score_mean_rank,
            threshold_retained_count=len(retained_thresh),
            threshold_lost_count=len(lost_thresh),
            final_top5_retained_count=len(retained_top5),
            final_top5_lost_count=len(lost_top5),
        )

        # Quality & Diversity Checks
        duplicates = len(rec_ids) - len(set(rec_ids))
        categories = {self.jobs[jid].category for jid in rec_ids if jid in self.jobs}
        cat_coverage = len(categories) / 5.0 if rec_ids else 0.0

        # Seniority compatibility
        from application.ai.extraction import SENIORITY_ORDINAL
        cand_sen = SENIORITY_ORDINAL.get(resume_doc.seniority_label.lower(), 1)
        sen_compat_scores = []
        for jid in rec_ids:
            if jid in self.jobs:
                j_sen = SENIORITY_ORDINAL.get(self.jobs[jid].seniority.lower(), 1)
                diff = abs(cand_sen - j_sen)
                sen_compat_scores.append(max(0.0, 1.0 - diff * 0.35))
        sen_compat = float(np.mean(sen_compat_scores)) if sen_compat_scores else 0.0

        # Skill compatibility
        cand_skills_l = {s.lower() for s in resume_doc.skill_candidates}
        skill_compat_scores = []
        matched_sample = []
        gaps_sample = []
        for _, _, job_obj, j_doc in final_top5:
            reqs = j_doc.required_skill_candidates
            if reqs:
                hits = sum(1 for s in reqs if s.lower() in cand_skills_l or any(c in s.lower() for c in cand_skills_l))
                ratio = hits / float(len(reqs))
                skill_compat_scores.append(ratio)
                for s in reqs:
                    if s.lower() in cand_skills_l:
                        matched_sample.append(s)
                    else:
                        gaps_sample.append(s)
            else:
                skill_compat_scores.append(1.0)
        skill_compat = float(np.mean(skill_compat_scores)) if skill_compat_scores else 0.0

        stage_breakdown = RecommendationPipelineStages(
            raw_retrieved_ids=raw_retrieved_ids,
            reranked_ids=reranked_ids,
            scored_ids=scored_ids,
            filtered_ids=filtered_ids,
            final_recommended_ids=rec_ids,
            final_scores=final_scores,
            lost_relevant_at_retrieval=lost_at_retrieval,
            lost_relevant_at_ranking=lost_at_ranking,
            lost_relevant_at_threshold=lost_at_threshold,
            unthresholded_recommended_ids=unthresh_rec_ids,
            funnel=funnel_report,
        )

        return RecommendationCaseResult(
            resume_id=resume_id,
            recommended_job_ids=rec_ids,
            match_scores=final_scores,
            relevant_job_ids=list(relevant_ids),
            graded_relevance=graded,
            precision_at_3=p3,
            precision_at_5=p5,
            recall_at_3=r3,
            recall_at_5=r5,
            hit_rate_at_5=hr5,
            mrr=mrr,
            ndcg_at_5=ndcg5,
            duplicate_count=duplicates,
            category_coverage=cat_coverage,
            skill_compatibility_score=skill_compat,
            seniority_compatibility_score=sen_compat,
            latency_ms=latency_ms,
            stages=stage_breakdown,
            matched_skills_sample=list(set(matched_sample))[:6],
            skill_gaps_sample=list(set(gaps_sample))[:6],
            n_relevant=n_rel,
            max_possible_precision_at_5=max_p5,
            max_possible_recall_at_5=max_r5,
            normalized_precision_at_5=norm_p5,
            normalized_recall_at_5=norm_r5,
            recall_at_20=r20,
            recall_at_50=r50,
            recall_at_100=r100,
            ndcg_at_10=ndcg10,
            average_precision=ap,
            r_precision=r_prec,
            unthresholded_recommended_ids=unthresh_rec_ids,
            unthresholded_precision_at_5=unthresh_p5,
            unthresholded_recall_at_5=unthresh_r5,
            unthresholded_normalized_precision_at_5=unthresh_norm_p5,
            unthresholded_normalized_recall_at_5=unthresh_norm_r5,
            unthresholded_ndcg_at_5=unthresh_ndcg5,
            unthresholded_mrr=unthresh_mrr,
            unthresholded_hit_rate_at_5=unthresh_hr5,
            funnel=funnel_report,
        )

    def evaluate_all(
        self,
        output_artifact_path: Optional[Path] = None,
        retrieval_k: int = 100,
    ) -> Tuple[RecommendationBenchmarkSummary, List[RecommendationCaseResult]]:
        self._ensure_pipeline()
        results: List[RecommendationCaseResult] = []
        failed: List[str] = []

        total_lost_retrieval = 0
        total_lost_threshold = 0

        for resume_id in sorted(self.resumes.keys()):
            if resume_id not in self.relevance_by_resume:
                continue
            try:
                res = self.evaluate_candidate(resume_id=resume_id, retrieval_k=retrieval_k)
                results.append(res)
                total_lost_retrieval += len(res.stages.lost_relevant_at_retrieval)
                total_lost_threshold += len(res.stages.lost_relevant_at_threshold)
            except Exception as exc:
                failed.append(resume_id)

        def safe_mean(values: List[float]) -> float:
            valid = [v for v in values if not math.isnan(v)]
            return float(np.mean(valid)) if valid else 0.0

        all_corpus_categories = {j.category for j in self.jobs.values() if j.category}
        all_rec_jobs = {jid for r in results for jid in r.recommended_job_ids}
        all_rec_categories = {self.jobs[jid].category for jid in all_rec_jobs if jid in self.jobs and self.jobs[jid].category}
        corpus_cat_cov = len(all_rec_categories) / float(len(all_corpus_categories)) if all_corpus_categories else 1.0
        corpus_job_cov = len(all_rec_jobs) / float(len(self.jobs)) if self.jobs else 0.0

        total_hits_3 = sum(sum(1 for j in r.recommended_job_ids[:3] if j in set(r.relevant_job_ids)) for r in results)
        total_hits_5 = sum(sum(1 for j in r.recommended_job_ids[:5] if j in set(r.relevant_job_ids)) for r in results)
        total_slots_3 = len(results) * 3
        total_slots_5 = len(results) * 5
        total_corpus_relevant = sum(len(r.relevant_job_ids) for r in results)

        micro_p3 = total_hits_3 / float(total_slots_3) if total_slots_3 else 0.0
        micro_p5 = total_hits_5 / float(total_slots_5) if total_slots_5 else 0.0
        micro_r3 = total_hits_3 / float(total_corpus_relevant) if total_corpus_relevant else 0.0
        micro_r5 = total_hits_5 / float(total_corpus_relevant) if total_corpus_relevant else 0.0

        stage_metrics = {}
        stage_id_getters = {
            "dense_retrieval": lambda result: result.stages.raw_retrieved_ids,
            "reranker": lambda result: result.stages.reranked_ids,
            "tabular_ranker": lambda result: result.stages.scored_ids,
            "final_recommendations": lambda result: result.stages.final_recommended_ids,
        }
        for stage_name, get_ids in stage_id_getters.items():
            stage_results = [
                _calculate_ranking_stage_metrics(
                    get_ids(result),
                    set(result.relevant_job_ids),
                    result.graded_relevance,
                )
                for result in results
            ]
            stage_metrics[stage_name] = RankingStageMetrics(
                precision_at_5=safe_mean([item["precision_at_5"] for item in stage_results]),
                recall_at_5=safe_mean([item["recall_at_5"] for item in stage_results]),
                hit_rate_at_5=safe_mean([item["hit_rate_at_5"] for item in stage_results]),
                mrr=safe_mean([item["mrr"] for item in stage_results]),
                ndcg_at_5=safe_mean([item["ndcg_at_5"] for item in stage_results]),
                ndcg_at_10=safe_mean([item["ndcg_at_10"] for item in stage_results]),
                map=safe_mean([item["map"] for item in stage_results]),
                r_precision=safe_mean([item["r_precision"] for item in stage_results]),
                recall_at_20=safe_mean([item["recall_at_20"] for item in stage_results]),
                recall_at_50=safe_mean([item["recall_at_50"] for item in stage_results]),
                recall_at_100=safe_mean([item["recall_at_100"] for item in stage_results]),
                normalized_precision_at_5=safe_mean([item["normalized_precision_at_5"] for item in stage_results]),
                normalized_recall_at_5=safe_mean([item["normalized_recall_at_5"] for item in stage_results]),
            )

        mean_p5 = safe_mean([r.precision_at_5 for r in results])
        mean_r5 = safe_mean([r.recall_at_5 for r in results])
        mean_ndcg5 = safe_mean([r.ndcg_at_5 for r in results])
        unthresh_mean_p5 = safe_mean([r.unthresholded_precision_at_5 for r in results])
        unthresh_mean_r5 = safe_mean([r.unthresholded_recall_at_5 for r in results])
        unthresh_mean_ndcg5 = safe_mean([r.unthresholded_ndcg_at_5 for r in results])

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
            "unthresholded_precision_at_5": bootstrap_ci([r.unthresholded_precision_at_5 for r in results]),
            "unthresholded_recall_at_5": bootstrap_ci([r.unthresholded_recall_at_5 for r in results]),
            "unthresholded_ndcg_at_5": bootstrap_ci([r.unthresholded_ndcg_at_5 for r in results]),
        }

        funnel_summary = {
            "total_corpus_relevant": sum(r.funnel.corpus_relevant_count for r in results if r.funnel),
            "retrieval_retained": sum(r.funnel.retrieval_retained_count for r in results if r.funnel),
            "retrieval_lost": sum(r.funnel.retrieval_lost_count for r in results if r.funnel),
            "retrieval_mean_rank": safe_mean([r.funnel.retrieval_mean_rank_relevant for r in results if r.funnel]),
            "rerank_mean_rank": safe_mean([r.funnel.rerank_mean_rank_relevant for r in results if r.funnel]),
            "score_mean_rank": safe_mean([r.funnel.score_mean_rank_relevant for r in results if r.funnel]),
            "threshold_retained": sum(r.funnel.threshold_retained_count for r in results if r.funnel),
            "threshold_lost": sum(r.funnel.threshold_lost_count for r in results if r.funnel),
            "final_top5_retained": sum(r.funnel.final_top5_retained_count for r in results if r.funnel),
            "final_top5_lost": sum(r.funnel.final_top5_lost_count for r in results if r.funnel),
        }

        summary = RecommendationBenchmarkSummary(
            total_candidates=len(results),
            mean_precision_at_3=safe_mean([r.precision_at_3 for r in results]),
            mean_precision_at_5=mean_p5,
            mean_recall_at_3=safe_mean([r.recall_at_3 for r in results]),
            mean_recall_at_5=mean_r5,
            micro_precision_at_3=micro_p3,
            micro_precision_at_5=micro_p5,
            micro_recall_at_3=micro_r3,
            micro_recall_at_5=micro_r5,
            mean_hit_rate_at_5=safe_mean([r.hit_rate_at_5 for r in results]),
            mean_mrr=safe_mean([r.mrr for r in results]),
            mean_ndcg_at_5=mean_ndcg5,
            duplicate_rate=safe_mean([float(r.duplicate_count) for r in results]),
            mean_category_coverage=safe_mean([r.category_coverage for r in results]),
            corpus_category_coverage=corpus_cat_cov,
            corpus_job_coverage=corpus_job_cov,
            mean_skill_compatibility=safe_mean([r.skill_compatibility_score for r in results]),
            mean_seniority_compatibility=safe_mean([r.seniority_compatibility_score for r in results]),
            mean_latency_ms=safe_mean([r.latency_ms for r in results]),
            total_lost_at_retrieval=total_lost_retrieval,
            total_lost_at_threshold=total_lost_threshold,
            failed_candidates=failed,
            stage_metrics=stage_metrics,
            mean_n_relevant=safe_mean([float(r.n_relevant) for r in results]),
            mean_max_possible_precision_at_5=safe_mean([r.max_possible_precision_at_5 for r in results]),
            mean_max_possible_recall_at_5=safe_mean([r.max_possible_recall_at_5 for r in results]),
            mean_normalized_precision_at_5=safe_mean([r.normalized_precision_at_5 for r in results]),
            mean_normalized_recall_at_5=safe_mean([r.normalized_recall_at_5 for r in results]),
            mean_recall_at_20=safe_mean([r.recall_at_20 for r in results]),
            mean_recall_at_50=safe_mean([r.recall_at_50 for r in results]),
            mean_recall_at_100=safe_mean([r.recall_at_100 for r in results]),
            mean_ndcg_at_10=safe_mean([r.ndcg_at_10 for r in results]),
            map=safe_mean([r.average_precision for r in results]),
            mean_r_precision=safe_mean([r.r_precision for r in results]),
            unthresholded_mean_precision_at_5=unthresh_mean_p5,
            unthresholded_mean_recall_at_5=unthresh_mean_r5,
            unthresholded_mean_normalized_precision_at_5=safe_mean([r.unthresholded_normalized_precision_at_5 for r in results]),
            unthresholded_mean_normalized_recall_at_5=safe_mean([r.unthresholded_normalized_recall_at_5 for r in results]),
            unthresholded_mean_ndcg_at_5=unthresh_mean_ndcg5,
            unthresholded_mean_mrr=safe_mean([r.unthresholded_mrr for r in results]),
            unthresholded_mean_hit_rate_at_5=safe_mean([r.unthresholded_hit_rate_at_5 for r in results]),
            threshold_cost_precision_delta=mean_p5 - unthresh_mean_p5,
            threshold_cost_recall_delta=mean_r5 - unthresh_mean_r5,
            threshold_cost_ndcg_delta=mean_ndcg5 - unthresh_mean_ndcg5,
            funnel_summary=funnel_summary,
            confidence_intervals=ci_metrics,
        )

        if output_artifact_path:
            output_artifact_path.parent.mkdir(parents=True, exist_ok=True)
            with output_artifact_path.open("x", encoding="utf-8") as f:
                for r in results:
                    f.write(json.dumps(asdict(r)) + "\n")

        return summary, results


def _calculate_ranking_stage_metrics(
    ranked_ids: List[str],
    relevant_ids: Set[str],
    graded_relevance: Dict[str, int],
) -> Dict[str, float]:
    return {
        "precision_at_5": calculate_precision_at_k(ranked_ids, relevant_ids, 5),
        "recall_at_5": calculate_recall_at_k(ranked_ids, relevant_ids, 5),
        "hit_rate_at_5": calculate_hit_rate_at_k(ranked_ids, relevant_ids, 5),
        "mrr": calculate_mrr(ranked_ids, relevant_ids),
        "ndcg_at_5": calculate_ndcg_at_k(ranked_ids, graded_relevance, 5),
        "ndcg_at_10": calculate_ndcg_at_k(ranked_ids, graded_relevance, 10),
        "map": calculate_average_precision(ranked_ids, relevant_ids),
        "r_precision": calculate_r_precision(ranked_ids, relevant_ids),
        "recall_at_20": calculate_recall_at_k(ranked_ids, relevant_ids, 20),
        "recall_at_50": calculate_recall_at_k(ranked_ids, relevant_ids, 50),
        "recall_at_100": calculate_recall_at_k(ranked_ids, relevant_ids, 100),
        "normalized_precision_at_5": calculate_normalized_precision_at_k(ranked_ids, relevant_ids, 5),
        "normalized_recall_at_5": calculate_normalized_recall_at_k(ranked_ids, relevant_ids, 5),
    }
