from unittest.mock import patch

from eval.src.retrieval_judge import (
    JudgeEvidence,
    RetrievalJudge,
    RetrievalJudgeOutput,
)


def test_missing_credentials_block_judgment_without_zero_grade():
    judge = RetrievalJudge(api_key="", dataset_version="test-v1")

    result = judge.evaluate_pair(
        {"skills": ["Python"]},
        {"title": "Python Developer", "required_skills": ["Python"]},
        case_id="case-1",
    )

    assert result.status == "BLOCKED"
    assert result.assessment is None
    assert result.error_code == "missing_credentials"


def test_judgment_caches_by_stable_input_hash_and_redacts_contact_details():
    judge = RetrievalJudge(api_key="test-key", dataset_version="golden-v1")
    output = RetrievalJudgeOutput(
        relevance_grade=3,
        confidence=0.9,
        matching_requirements=[
            JudgeEvidence(
                requirement="Python",
                evidence="Built a Python API",
                reason="The resume directly demonstrates the required skill.",
            )
        ],
        supporting_evidence=["Built a Python API"],
        reason="The candidate has direct evidence for a core requirement.",
    )
    with patch.object(judge, "_request_judgment", return_value=(output, 100, 25)) as request:
        candidate = {
            "name": "Private Name",
            "email": "candidate@example.com",
            "skills": [{"skill": "Python", "evidence": "Built a Python API"}],
        }
        job = {"title": "Python Developer", "required_skills": ["Python"]}
        first = judge.evaluate_pair(candidate, job, case_id="case-2")
        second = judge.evaluate_pair(candidate, job, case_id="case-2")

    assert first.status == "COMPLETED"
    assert first.input_tokens == 100
    assert first.output_tokens == 25
    assert first.cost_usd is None
    assert second.cache_hit
    assert first.input_hash == second.input_hash
    request.assert_called_once()
    request_payload = request.call_args.args[0]
    assert "candidate@example.com" not in str(request_payload)
    assert "Private Name" not in str(request_payload)


def test_judge_discards_grade_when_its_citation_is_unsupported():
    judge = RetrievalJudge(api_key="test-key", dataset_version="golden-v1")
    output = RetrievalJudgeOutput(
        relevance_grade=3,
        confidence=1.0,
        matching_requirements=[
            JudgeEvidence(
                requirement="AWS",
                evidence="Deployed production workloads to AWS",
            )
        ],
        reason="The candidate has the required experience.",
    )
    with patch.object(judge, "_request_judgment", return_value=(output, 100, 25)):
        result = judge.evaluate_pair(
            {"skills": [{"skill": "Python", "evidence": "Built a Python API"}]},
            {"title": "Cloud Engineer", "required_skills": ["AWS"]},
        )

    assert result.status == "ERROR"
    assert result.assessment is None
    assert result.error_code == "unsupported_evidence"
