from __future__ import annotations

import json
import math
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import numpy as np

from eval.src.data_loader import GoldenDataLoader, GoldenResume, GoldenResumeSummary
from eval.src.deepeval_metrics import (
    DeepEvalMetricHarness,
    DeterministicGroundednessChecker,
    build_deepeval_test_case,
)


@dataclass
class SummaryCaseResult:
    case_id: str
    resume_id: str
    audience: str
    actual_summary: str
    expected_summary: str
    schema_valid: bool
    context_groundedness_score: float
    query_term_coverage_score: float
    faithfulness_score: Optional[float]
    relevancy_score: Optional[float]
    geval_score: Optional[float]
    llm_judge_status: str
    hallucination_detected: bool
    hallucinated_claims: List[str]
    missing_required_facts: List[str]
    passed: bool
    latency_ms: float
    extracted_skills: List[str] = field(default_factory=list)
    education_summary: str = ""
    experience_highlights: List[str] = field(default_factory=list)


@dataclass
class SummaryBenchmarkSummary:
    total_summaries: int
    schema_validity_rate: float
    mean_context_groundedness: float
    mean_query_term_coverage: float
    hallucination_rate: float
    factual_completeness_rate: float
    deterministic_pass_rate: float
    mean_faithfulness: Optional[float]
    mean_relevancy: Optional[float]
    mean_geval: Optional[float]
    llm_judge_status: str
    mean_latency_ms: float
    failed_cases: List[str] = field(default_factory=list)


class ResumeSummaryEvaluator:
    """Evaluates CareerConnect's production resume analysis and summarization workflow."""

    def __init__(
        self,
        loader: Optional[GoldenDataLoader] = None,
        pipeline_instance: Optional[Any] = None,
        deepeval_harness: Optional[DeepEvalMetricHarness] = None,
    ):
        self.loader = loader or GoldenDataLoader()
        self.resumes = self.loader.load_resumes()
        self.summaries = self.loader.load_summaries()
        self.pipeline = pipeline_instance
        self.deepeval_harness = deepeval_harness or DeepEvalMetricHarness()

    def _ensure_pipeline(self) -> None:
        if self.pipeline is None:
            from application.ai.pipeline import MatchingPipeline
            self.pipeline = MatchingPipeline.get_default()

    def evaluate_summary(
        self,
        gold_summary: GoldenResumeSummary,
    ) -> SummaryCaseResult:
        self._ensure_pipeline()
        resume = self.resumes.get(gold_summary.resume_id)
        if not resume:
            raise ValueError(f"Resume {gold_summary.resume_id} not found.")

        t0 = time.perf_counter()

        # Ingest through production pipeline
        cleaned_resume = self.pipeline.cleaner(resume.resume_text)
        resume_doc = self.pipeline.resume_parser.parse(cleaned_resume, raw_text=resume.resume_text)

        norm = self.pipeline.normalizer.normalize_list
        ex = self.pipeline.skill_extractor.extract

        core_skills = ex(resume_doc.skills_section or cleaned_resume)
        resume_doc.skill_candidates = norm(core_skills)
        resume_doc.years_experience = self.pipeline.experience_extractor.extract(
            resume_doc.experience_section or cleaned_resume
        )
        resume_doc.degree_level = self.pipeline.education_extractor.extract(
            resume_doc.education_section or cleaned_resume
        )
        resume_doc.education_details = self.pipeline.education_extractor.extract_details(
            resume_doc.education_section or cleaned_resume
        )
        resume_doc.seniority_label = self.pipeline.seniority_extractor.extract(
            cleaned_resume,
            years_experience=resume_doc.years_experience,
            degree_level=resume_doc.degree_level,
        )

        from application.ai.pipeline import (
            build_candidate_summary,
            build_education_summary,
            build_experience_highlights,
        )

        actual_summary = build_candidate_summary(resume_doc, candidate_name=resume.candidate_name)
        edu_summary = build_education_summary(resume_doc)
        exp_highlights = build_experience_highlights(resume_doc)

        latency_ms = (time.perf_counter() - t0) * 1000.0

        # 1. Output Schema Validation
        schema_valid = (
            bool(actual_summary)
            and isinstance(actual_summary, str)
            and len(actual_summary) >= 15
            and bool(edu_summary)
            and isinstance(exp_highlights, list)
        )

        # 2. Deterministic Groundedness & Overlap
        context_groundedness, _ = DeterministicGroundednessChecker.compute_context_groundedness(
            actual_summary,
            [resume.resume_text[:1200]],
        )
        query_prompt = f"Generate a concise {gold_summary.audience} resume summary for candidate {resume.candidate_name}."
        query_coverage, _ = DeterministicGroundednessChecker.compute_query_term_coverage(
            actual_summary,
            query_prompt,
        )

        # 3. Hallucination Checks (Must Not Claim)
        hallucinated_claims = []
        combined_output = f"{actual_summary} {edu_summary} {' '.join(exp_highlights)}".lower()

        for forbidden in gold_summary.must_not_claim:
            if forbidden.lower() in combined_output:
                hallucinated_claims.append(forbidden)

        # Degree hallucination check
        expected_deg = resume.degree_level
        if expected_deg == 2 and ("doctorate" in combined_output or "ph.d" in combined_output):
            hallucinated_claims.append("Hallucinated Ph.D. degree")

        # Experience inflation check
        exp = resume.experience_years or 0.0
        if exp < 2.0 and re.search(r"\b[5-9]\+?\s*years", combined_output):
            hallucinated_claims.append("Inflated years of experience (>5 yrs)")

        # 4. Completeness Checks (Must Include)
        missing_required_facts = []
        for required_item in gold_summary.must_include:
            if required_item and required_item.lower() not in combined_output:
                missing_required_facts.append(required_item)

        # 5. DeepEval Test Case
        test_case = build_deepeval_test_case(
            input_text=query_prompt,
            actual_output=actual_summary,
            expected_output=gold_summary.expected_summary,
            retrieval_context=[resume.resume_text[:1200]],
            context=[resume.resume_text[:1200]],
        )
        eval_res = self.deepeval_harness.evaluate_test_case(gold_summary.case_id, test_case)

        has_hallucination = len(hallucinated_claims) > 0
        overall_passed = (
            schema_valid
            and not has_hallucination
            and len(missing_required_facts) <= 1
            and context_groundedness >= 0.70
        )

        return SummaryCaseResult(
            case_id=gold_summary.case_id,
            resume_id=gold_summary.resume_id,
            audience=gold_summary.audience,
            actual_summary=actual_summary,
            expected_summary=gold_summary.expected_summary,
            schema_valid=schema_valid,
            context_groundedness_score=context_groundedness,
            query_term_coverage_score=query_coverage,
            faithfulness_score=eval_res.faithfulness_score,
            relevancy_score=eval_res.answer_relevancy_score,
            geval_score=eval_res.geval_score,
            llm_judge_status=eval_res.status,
            hallucination_detected=has_hallucination,
            hallucinated_claims=hallucinated_claims,
            missing_required_facts=missing_required_facts,
            passed=overall_passed,
            latency_ms=latency_ms,
            extracted_skills=resume_doc.skill_candidates[:8],
            education_summary=edu_summary,
            experience_highlights=exp_highlights,
        )

    def evaluate_all(
        self,
        output_artifact_path: Optional[Path] = None,
    ) -> Tuple[SummaryBenchmarkSummary, List[SummaryCaseResult]]:
        self._ensure_pipeline()
        results: List[SummaryCaseResult] = []
        failed_cases: List[str] = []

        for item in self.summaries:
            try:
                res = self.evaluate_summary(item)
                results.append(res)
                if not res.passed:
                    failed_cases.append(item.case_id)
            except Exception as exc:
                failed_cases.append(item.case_id)

        n = float(len(results))
        llm_status = results[0].llm_judge_status if results else "NOT_RUN"

        valid_faith = [r.faithfulness_score for r in results if r.faithfulness_score is not None]
        mean_faith = float(np.mean(valid_faith)) if valid_faith else None

        valid_rel = [r.relevancy_score for r in results if r.relevancy_score is not None]
        mean_rel = float(np.mean(valid_rel)) if valid_rel else None

        valid_geval = [r.geval_score for r in results if r.geval_score is not None]
        mean_geval = float(np.mean(valid_geval)) if valid_geval else None

        summary = SummaryBenchmarkSummary(
            total_summaries=len(results),
            schema_validity_rate=sum(1 for r in results if r.schema_valid) / n if results else 0.0,
            mean_context_groundedness=float(np.mean([r.context_groundedness_score for r in results])) if results else 0.0,
            mean_query_term_coverage=float(np.mean([r.query_term_coverage_score for r in results])) if results else 0.0,
            hallucination_rate=sum(1 for r in results if r.hallucination_detected) / n if results else 0.0,
            factual_completeness_rate=sum(1 for r in results if len(r.missing_required_facts) == 0) / n if results else 0.0,
            deterministic_pass_rate=sum(1 for r in results if r.passed) / n if results else 0.0,
            mean_faithfulness=mean_faith,
            mean_relevancy=mean_rel,
            mean_geval=mean_geval,
            llm_judge_status=llm_status,
            mean_latency_ms=float(np.mean([r.latency_ms for r in results])) if results else 0.0,
            failed_cases=failed_cases,
        )

        if output_artifact_path:
            output_artifact_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_artifact_path, "w", encoding="utf-8") as f:
                for r in results:
                    f.write(json.dumps(asdict(r)) + "\n")

        return summary, results
