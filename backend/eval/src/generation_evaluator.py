from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from eval.src.data_loader import GoldenDataLoader, GoldenJob, GoldenRecommendation, GoldenResume
from eval.src.deepeval_metrics import (
    DeepEvalMetricHarness,
    DeterministicGroundednessChecker,
    build_deepeval_test_case,
)


@dataclass
class ExplanationCaseResult:
    case_id: str
    resume_id: str
    job_id: str
    match_score: int
    matching_points: List[str]
    gap_points: List[str]
    recommendation_text: str
    token_groundedness_score: float
    factual_claims_groundedness: float
    grounded_skills_rate: float
    grounded_gaps_rate: float
    faithfulness_score: Optional[float]
    relevancy_score: Optional[float]
    geval_score: Optional[float]
    llm_judge_status: str  # "COMPLETED", "BLOCKED_NO_CREDENTIALS", or "TEST_MOCK"
    passed: bool
    latency_ms: float
    errors: List[str] = field(default_factory=list)


@dataclass
class GenerationBenchmarkSummary:
    total_evaluations: int
    mean_token_groundedness: float
    mean_factual_claims_groundedness: float
    mean_grounded_skills_rate: float
    mean_grounded_gaps_rate: float
    deterministic_pass_rate: float
    mean_faithfulness: Optional[float]
    mean_relevancy: Optional[float]
    mean_geval: Optional[float]
    llm_judge_status: str
    mean_latency_ms: float
    failed_cases: List[str] = field(default_factory=list)


class GenerationEvaluator:
    """Evaluates recommendation explanations, evidence groundedness, and DeepEval metrics."""

    def __init__(
        self,
        loader: Optional[GoldenDataLoader] = None,
        pipeline_instance: Optional[Any] = None,
        deepeval_harness: Optional[DeepEvalMetricHarness] = None,
    ):
        self.loader = loader or GoldenDataLoader()
        self.jobs = self.loader.load_jobs()
        self.resumes = self.loader.load_resumes()
        self.recommendations = self.loader.load_recommendations()
        self.pipeline = pipeline_instance
        self.deepeval_harness = deepeval_harness or DeepEvalMetricHarness()

    def _ensure_pipeline(self) -> None:
        if self.pipeline is None:
            from application.ai.pipeline import MatchingPipeline
            self.pipeline = MatchingPipeline.get_default()

    def evaluate_pair(
        self,
        recommendation: GoldenRecommendation,
    ) -> ExplanationCaseResult:
        self._ensure_pipeline()
        resume = self.resumes.get(recommendation.resume_id)
        job = self.jobs.get(recommendation.job_id)
        if not resume or not job:
            raise ValueError(f"Pair not found: {recommendation.resume_id} - {recommendation.job_id}")

        t0 = time.perf_counter()

        cleaned_resume = self.pipeline.cleaner(resume.resume_text)
        cleaned_job = self.pipeline.cleaner(job.description)
        resume_doc = self.pipeline.resume_parser.parse(cleaned_resume, raw_text=resume.resume_text)
        job_doc = self.pipeline.job_parser.parse(clean_text=cleaned_job, title=job.title, raw_text=job.description)

        norm = self.pipeline.normalizer.normalize_list
        ex = self.pipeline.skill_extractor.extract

        core_skills = ex(resume_doc.skills_section or cleaned_resume)
        resume_doc.skill_candidates = norm(core_skills)
        job_doc.required_skill_candidates = norm(ex(job_doc.required_skills_section or cleaned_job))
        job_doc.preferred_skill_candidates = norm(ex(job_doc.preferred_skills_section or "")) if job_doc.preferred_skills_section else []
        resume_doc.years_experience = self.pipeline.experience_extractor.extract(
            resume_doc.experience_section or cleaned_resume
        )
        job_doc.required_years = self.pipeline.experience_extractor.extract(
            job_doc.experience_requirements_section or cleaned_job
        )
        resume_doc.degree_level = self.pipeline.education_extractor.extract(cleaned_resume)
        job_doc.required_degree_level = self.pipeline.education_extractor.extract(cleaned_job)
        resume_doc.seniority_label = self.pipeline.seniority_extractor.extract(
            cleaned_resume,
            years_experience=resume_doc.years_experience,
            degree_level=resume_doc.degree_level,
        )
        job_doc.seniority_label = self.pipeline.seniority_extractor.extract(
            f"{job.title}\n{cleaned_job[:400]}",
            years_experience=job_doc.required_years,
            degree_level=job_doc.required_degree_level,
        )

        emb_res = self.pipeline.embedding.embed_text(cleaned_resume[:1000])
        emb_job = self.pipeline.embedding.embed_text(cleaned_job[:1000])
        ce_score = self.pipeline.reranker.predict_pair(cleaned_job, cleaned_resume)

        features = self.pipeline.feature_extractor.extract(
            resume_doc=resume_doc,
            job_doc=job_doc,
            resume_embedding=emb_res,
            job_embedding=emb_job,
            cross_encoder_score=ce_score,
        )
        match_score = int(round(self.pipeline.ranker.score(features)))
        matches_ev, gaps_ev = self.pipeline.evidence_generator.generate(features, resume_doc, job_doc)

        from application.ai.pipeline import build_recommendation
        rec_text = build_recommendation(match_score)

        latency_ms = (time.perf_counter() - t0) * 1000.0

        match_points = [m.point for m in matches_ev]
        gap_points = [g.point for g in gaps_ev]

        # 1. Deterministic Groundedness & Evidence Checks
        resume_lower = resume.resume_text.lower()
        job_lower = job.description.lower()

        skill_match_points = [
            mp for mp in match_points
            if mp.startswith("Has required skill:") or mp.startswith("Has preferred skill:")
        ]
        grounded_skills = 0
        for mp in skill_match_points:
            skill_part = mp.split(":", 1)[1].strip().lower()
            if skill_part in resume_lower or any(s in resume_lower for s in skill_part.split() if len(s) > 2):
                grounded_skills += 1
        grounded_skills_rate = grounded_skills / float(len(skill_match_points)) if skill_match_points else 1.0

        skill_gap_points = [
            gp for gp in gap_points
            if gp.startswith("Missing required skill:") or gp.startswith("Missing preferred skill:")
        ]
        grounded_gaps = 0
        for gp in skill_gap_points:
            gap_part = gp.split(":", 1)[1].strip().lower()
            if gap_part in job_lower or any(s in job_lower for s in gap_part.split() if len(s) > 2):
                grounded_gaps += 1
        grounded_gaps_rate = grounded_gaps / float(len(skill_gap_points)) if skill_gap_points else 1.0

        explanation_body = f"Matching skills: {', '.join(match_points[:4])}. Gaps: {', '.join(gap_points[:3])}. Recommendation: {rec_text}"

        token_groundedness, _ = DeterministicGroundednessChecker.compute_context_groundedness(
            explanation_body,
            [job.description[:600], resume.resume_text[:600]],
        )

        claims_text = f"{', '.join(match_points[:4])}. {', '.join(gap_points[:3])}"
        factual_claims_groundedness, _ = DeterministicGroundednessChecker.compute_context_groundedness(
            claims_text,
            [job.description[:600], resume.resume_text[:600]],
        )

        # 2. DeepEval Evaluation
        test_case = build_deepeval_test_case(
            input_text=f"Explain match between candidate for job {job.title}",
            actual_output=explanation_body,
            expected_output=recommendation.reference_reasoning,
            retrieval_context=[f"{job.description[:600]}", f"{resume.resume_text[:600]}"],
            context=[f"{job.description[:600]}", f"{resume.resume_text[:600]}"],
        )
        eval_res = self.deepeval_harness.evaluate_test_case(recommendation.case_id, test_case)

        # Deterministic pass definition
        deterministic_passed = (
            grounded_skills_rate >= 0.75
            and grounded_gaps_rate >= 0.75
            and token_groundedness >= 0.65
        )

        return ExplanationCaseResult(
            case_id=recommendation.case_id,
            resume_id=recommendation.resume_id,
            job_id=recommendation.job_id,
            match_score=match_score,
            matching_points=match_points,
            gap_points=gap_points,
            recommendation_text=rec_text,
            token_groundedness_score=token_groundedness,
            factual_claims_groundedness=factual_claims_groundedness,
            grounded_skills_rate=grounded_skills_rate,
            grounded_gaps_rate=grounded_gaps_rate,
            faithfulness_score=eval_res.faithfulness_score,
            relevancy_score=eval_res.answer_relevancy_score,
            geval_score=eval_res.geval_score,
            llm_judge_status=eval_res.status,
            passed=deterministic_passed,
            latency_ms=latency_ms,
        )

    def evaluate_all(
        self,
        output_artifact_path: Optional[Path] = None,
        max_cases: int = 50,
    ) -> Tuple[GenerationBenchmarkSummary, List[ExplanationCaseResult]]:
        self._ensure_pipeline()
        results: List[ExplanationCaseResult] = []
        failed_cases: List[str] = []

        eval_subset = self.recommendations[:max_cases]
        for rec in eval_subset:
            try:
                res = self.evaluate_pair(rec)
                results.append(res)
                if not res.passed:
                    failed_cases.append(rec.case_id)
            except Exception as exc:
                failed_cases.append(rec.case_id)

        n = float(len(results))
        llm_status = results[0].llm_judge_status if results else "NOT_RUN"

        # Calculate means
        mean_token_g = float(np.mean([r.token_groundedness_score for r in results])) if results else 0.0
        mean_claims_g = float(np.mean([r.factual_claims_groundedness for r in results])) if results else 0.0
        mean_skills_r = float(np.mean([r.grounded_skills_rate for r in results])) if results else 0.0
        mean_gaps_r = float(np.mean([r.grounded_gaps_rate for r in results])) if results else 0.0
        det_pass_r = sum(1 for r in results if r.passed) / n if results else 0.0
        mean_lat = float(np.mean([r.latency_ms for r in results])) if results else 0.0

        valid_faith = [r.faithfulness_score for r in results if r.faithfulness_score is not None]
        mean_faith = float(np.mean(valid_faith)) if valid_faith else None

        valid_rel = [r.relevancy_score for r in results if r.relevancy_score is not None]
        mean_rel = float(np.mean(valid_rel)) if valid_rel else None

        valid_geval = [r.geval_score for r in results if r.geval_score is not None]
        mean_geval = float(np.mean(valid_geval)) if valid_geval else None

        summary = GenerationBenchmarkSummary(
            total_evaluations=len(results),
            mean_token_groundedness=mean_token_g,
            mean_factual_claims_groundedness=mean_claims_g,
            mean_grounded_skills_rate=mean_skills_r,
            mean_grounded_gaps_rate=mean_gaps_r,
            deterministic_pass_rate=det_pass_r,
            mean_faithfulness=mean_faith,
            mean_relevancy=mean_rel,
            mean_geval=mean_geval,
            llm_judge_status=llm_status,
            mean_latency_ms=mean_lat,
            failed_cases=failed_cases,
        )

        if output_artifact_path:
            output_artifact_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_artifact_path, "w", encoding="utf-8") as f:
                for r in results:
                    f.write(json.dumps(asdict(r)) + "\n")

        return summary, results
