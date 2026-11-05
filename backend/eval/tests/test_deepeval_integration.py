from __future__ import annotations

import pytest
from deepeval.test_case import LLMTestCase
from eval.src.deepeval_metrics import (
    DeepEvalMetricHarness,
    DeterministicGroundednessChecker,
    MockOfflineJudge,
    build_deepeval_test_case,
    is_llm_api_configured,
)


def test_deepeval_test_case_builder():
    case = build_deepeval_test_case(
        input_text="Summarize candidate profile.",
        actual_output="Aarav Sharma is an early-career engineer skilled in Python and PyTorch.",
        expected_output="Candidate has experience in Python and PyTorch.",
        retrieval_context=["Candidate resume shows 2 projects in PyTorch."],
    )
    assert isinstance(case, LLMTestCase)
    assert case.input == "Summarize candidate profile."
    assert "PyTorch" in case.actual_output
    assert len(case.retrieval_context) == 1


def test_deepeval_harness_blocked_when_no_credentials():
    # When no external LLM key is configured and allow_test_mock=False:
    # Harness must explicitly report BLOCKED and return None for LLM scores
    harness = DeepEvalMetricHarness(allow_test_mock=False)
    if not is_llm_api_configured():
        assert harness.is_online is False
        assert harness.judge_mode == "blocked_missing_credentials"

        case = build_deepeval_test_case(
            input_text="Summarize candidate.",
            actual_output="Candidate has Python skills.",
            retrieval_context=["Candidate has Python skills."],
        )
        res = harness.evaluate_test_case("CASE_BLOCKED_001", case)
        assert res.status == "BLOCKED"
        assert res.faithfulness_score is None
        assert res.answer_relevancy_score is None
        assert res.geval_score is None
        assert "BLOCKED" in res.reasons["status"]


def test_deepeval_harness_unit_test_mock_mode():
    # Explicitly test harness plumbing with mock judge in unit test mode
    harness = DeepEvalMetricHarness(allow_test_mock=True)
    assert harness.judge_mode == "test_mock"
    assert isinstance(harness.judge_model, MockOfflineJudge)

    case = build_deepeval_test_case(
        input_text="Summarize candidate background with Python and PyTorch.",
        actual_output="Python engineer with PyTorch and computer vision projects.",
        retrieval_context=["Candidate is a Python engineer with PyTorch and computer vision projects."],
    )
    res = harness.evaluate_test_case("CASE_TEST_001", case)
    assert res.case_id == "CASE_TEST_001"
    assert res.status == "COMPLETED"
    assert res.judge_mode == "test_mock"
    assert res.faithfulness_score is not None


def test_deterministic_groundedness_checker():
    context = ["Aarav Sharma is a Machine Learning Engineer Intern with Python and PyTorch."]
    # Grounded output
    supported_output = "Aarav Sharma works with Python and PyTorch deep learning."
    score, reason = DeterministicGroundednessChecker.compute_context_groundedness(supported_output, context)
    assert score > 0.60
    assert "found in context" in reason

    # Completely ungrounded output
    unsupported_output = "Kubernetes cluster architecture with Golang microservices and Terraform."
    score_unsupported, _ = DeterministicGroundednessChecker.compute_context_groundedness(unsupported_output, context)
    assert score_unsupported == 0.0
