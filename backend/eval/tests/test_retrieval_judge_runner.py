import json

import pytest

from eval.src.data_loader import GoldenDataLoader, GoldenRecommendation
from eval.scripts.run_retrieval_judge import run_judge_sample, select_stratified_sample


def test_stratified_sample_is_deterministic_and_balanced():
    cases = [
        GoldenRecommendation(
            case_id=f"{grade}-{index}",
            resume_id="resume",
            job_id="job",
            relevance=grade,
            relevant_for_recommendation=grade >= 2,
            reference_reasoning="test",
        )
        for grade in range(4)
        for index in range(6)
    ]

    first = select_stratified_sample(cases, per_grade=2, seed=7)
    second = select_stratified_sample(cases, per_grade=2, seed=7)

    assert [case.case_id for case in first] == [case.case_id for case in second]
    assert {grade: sum(case.relevance == grade for case in first) for grade in range(4)} == {
        0: 2,
        1: 2,
        2: 2,
        3: 2,
    }


def test_stratified_sample_rejects_nonpositive_sample_size():
    with pytest.raises(ValueError, match="per_grade must be positive"):
        select_stratified_sample([], per_grade=0)


def test_runner_records_blocked_results_and_never_overwrites(tmp_path):
    dataset_dir = tmp_path / "datasets"
    dataset_dir.mkdir()
    (dataset_dir / "golden_resumes.jsonl").write_text(
        '{"resume_id":"r1","resume_text":"Python APIs","candidate_profile":{"skills":["Python"]}}\n',
        encoding="utf-8",
    )
    (dataset_dir / "golden_jobs.jsonl").write_text(
        '{"job_id":"j1","title":"Python Developer","description":"Build Python APIs","required_skills":["Python"]}\n',
        encoding="utf-8",
    )
    (dataset_dir / "golden_recommendations.jsonl").write_text(
        '{"case_id":"c1","resume_id":"r1","job_id":"j1","relevance":3,"relevant_for_recommendation":true,"reference_reasoning":"match"}\n',
        encoding="utf-8",
    )
    output_path = tmp_path / "judge.jsonl"

    written_path = run_judge_sample(
        per_grade=1,
        output_path=output_path,
        loader=GoldenDataLoader(dataset_dir=dataset_dir),
        api_key="",
    )

    assert written_path == output_path
    result = json.loads(output_path.read_text(encoding="utf-8"))
    assert result["judge_result"]["status"] == "BLOCKED"
    with pytest.raises(FileExistsError):
        run_judge_sample(
            per_grade=1,
            output_path=output_path,
            loader=GoldenDataLoader(dataset_dir=dataset_dir),
            api_key="",
        )
