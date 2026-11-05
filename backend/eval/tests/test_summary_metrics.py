from __future__ import annotations

import pytest
from eval.src.data_loader import GoldenDataLoader, GoldenResumeSummary
from eval.src.resume_summary_evaluator import ResumeSummaryEvaluator


def test_resume_summary_evaluator_valid_case():
    loader = GoldenDataLoader()
    evaluator = ResumeSummaryEvaluator(loader=loader)
    
    # Evaluate SUMMARY_0001
    gold_sum = loader.load_summaries()[0]
    res = evaluator.evaluate_summary(gold_sum)

    assert res.case_id == gold_sum.case_id
    assert res.schema_valid is True
    assert res.context_groundedness_score > 0.60
    assert res.hallucination_detected is False
    assert len(res.hallucinated_claims) == 0
    assert len(res.extracted_skills) > 0
    assert res.llm_judge_status in ("COMPLETED", "BLOCKED")


def test_hallucination_detection_triggers():
    loader = GoldenDataLoader()
    evaluator = ResumeSummaryEvaluator(loader=loader)

    # Construct synthetic case with forbidden claim that appears in output
    gold_sum = GoldenResumeSummary(
        case_id="TEST_SUM_HALLUCINATION",
        resume_id="RES_0006",
        audience="recruiter",
        expected_summary="Expected summary text here...",
        reference_facts=["Candidate has Python experience."],
        must_include=["Python"],
        must_not_claim=["FastAPI"],  # "FastAPI" appears in candidate output and should trigger detection
    )
    res = evaluator.evaluate_summary(gold_sum)
    # Must correctly detect that forbidden claim appeared
    assert res.hallucination_detected is True
    assert "FastAPI" in res.hallucinated_claims


def test_skill_extraction_parenthetical_and_alias_normalization():
    from application.ai.extraction import SkillExtractionPipeline, SkillNormalizer

    extractor = SkillExtractionPipeline()
    normalizer = SkillNormalizer()

    raw_text = (
        "Languages: Java (8/11/17), Go (Golang), Modern C++ (17/20), Python (Pandas, NumPy)\n"
        "Mobile: Android SDK, Jetpack Compose\n"
        "Security: Cybersecurity, SIEM, Incident Response"
    )
    extracted = extractor.extract(raw_text)
    normalized = normalizer.normalize_list(extracted)
    norm_set = {s.lower() for s in normalized}

    # Must cleanly normalize parentheticals without broken tokens like 'Java (8' or 'Modern C++ (17'
    assert "java" in norm_set
    assert "go" in norm_set
    assert "c++" in norm_set
    assert "python" in norm_set
    assert "android" in norm_set
    assert "cybersecurity" in norm_set
    assert "java (8" not in norm_set
    assert "modern c++ (17" not in norm_set


def test_education_degree_regex_prefix_integrity():
    from application.ai.extraction import EducationExtractor

    extractor = EducationExtractor()
    # Ensure 'Bachelor of Technology' is parsed as Bachelor of Technology (level 2), not truncated to 'Ba'
    details = extractor.extract_details("Completed Bachelor of Technology in Computer Science from VJTI.")
    assert len(details) > 0
    assert "Bachelor of Technology" in details[0].degree
    assert details[0].degree != "Ba"

    # Master of Science should not match 'Ma'
    details_ms = extractor.extract_details("Earned Master of Science in Data Analytics from Stanford.")
    assert len(details_ms) > 0
    assert "Master of Science" in details_ms[0].degree
    assert details_ms[0].degree != "Ma"


def test_build_candidate_summary_prioritizes_core_languages():
    from application.ai.pipeline import build_candidate_summary
    from application.ai.parsing import ResumeDocument

    doc = ResumeDocument(
        clean_text="Python developer with experience building deep learning models using PyTorch, LangChain, LangGraph, RAG, and FastAPI.",
        raw_text="",
        skill_candidates=["DeepEval", "LangChain", "LangGraph", "RAG", "Docker", "Python", "PyTorch"],
        years_experience=3.0,
        seniority_label="Mid",
        degree_level=2,
    )
    summary = build_candidate_summary(doc, candidate_name="Rohan Deshmukh")
    # Python must be prioritized in top skills rather than omitted due to framework list length
    assert "Python" in summary
    assert "Rohan Deshmukh" in summary
    assert "3+ years" in summary


def test_build_candidate_summary_empty_inputs_graceful():
    from application.ai.pipeline import build_candidate_summary
    from application.ai.parsing import ResumeDocument

    empty_doc = ResumeDocument(
        clean_text="",
        raw_text="",
        skill_candidates=[],
        years_experience=0.0,
        seniority_label="",
        degree_level=0,
    )
    summary = build_candidate_summary(empty_doc, candidate_name="Jane Doe")
    assert "Jane Doe" in summary
    assert "early-career" in summary
    assert "software engineering" in summary


def test_build_candidate_summary_missing_degree_no_hallucination():
    from application.ai.pipeline import build_candidate_summary
    from application.ai.parsing import ResumeDocument

    doc_no_degree = ResumeDocument(
        clean_text="Self-taught programmer with 2 years building React and TypeScript applications.",
        raw_text="",
        skill_candidates=["React", "TypeScript"],
        years_experience=2.0,
        seniority_label="Junior",
        degree_level=0,
        education_details=[],
    )
    summary = build_candidate_summary(doc_no_degree, candidate_name="Alex Smith")
    assert "Alex Smith" in summary
    assert "2+ years" in summary
    assert "React" in summary
    # Must not claim or hallucinate a degree when none is present
    assert "Holds" not in summary
    assert "Degree" not in summary
