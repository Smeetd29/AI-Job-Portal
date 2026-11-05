from __future__ import annotations

import json
import pytest
from pathlib import Path
from eval.src.dataset_validation import DatasetValidator, DatasetValidationError


def test_production_golden_datasets_pass_validation():
    """Verify that the production golden dataset passes all structural & relational constraints."""
    validator = DatasetValidator()
    counts = validator.validate_all()
    assert counts["jobs_count"] >= 50
    assert counts["resumes_count"] >= 30
    assert counts["recommendations_count"] >= 200
    assert counts["summaries_count"] >= 30


def test_validator_rejects_invalid_json(tmp_path: Path):
    bad_file = tmp_path / "golden_jobs.jsonl"
    bad_file.write_text("{invalid json", encoding="utf-8")
    validator = DatasetValidator(dataset_dir=tmp_path)
    with pytest.raises(DatasetValidationError, match="Invalid JSON"):
        validator.validate_jobs(bad_file)


def test_validator_rejects_missing_fields(tmp_path: Path):
    bad_file = tmp_path / "golden_jobs.jsonl"
    bad_file.write_text(json.dumps({"job_id": "JOB_0001"}) + "\n", encoding="utf-8")
    validator = DatasetValidator(dataset_dir=tmp_path)
    with pytest.raises(DatasetValidationError, match="Schema error"):
        validator.validate_jobs(bad_file)


def test_validator_rejects_duplicate_job_ids(tmp_path: Path):
    bad_file = tmp_path / "golden_jobs.jsonl"
    record = {
        "job_id": "JOB_0001",
        "title": "Software Engineer",
        "company": "Tech Corp",
        "description": "Valid job description longer than twenty characters...",
        "required_skills": ["Python"],
        "minimum_experience_years": 1.0,
        "seniority": "Junior"
    }
    bad_file.write_text(json.dumps(record) + "\n" + json.dumps(record) + "\n", encoding="utf-8")
    validator = DatasetValidator(dataset_dir=tmp_path)
    with pytest.raises(DatasetValidationError, match="Duplicate job_id"):
        validator.validate_jobs(bad_file)


def test_validator_rejects_invalid_references(tmp_path: Path):
    recs_file = tmp_path / "golden_recommendations.jsonl"
    rec = {
        "case_id": "MATCH_0001",
        "resume_id": "RES_NONEXISTENT",
        "job_id": "JOB_0001",
        "relevance": 3,
        "relevant_for_recommendation": True,
        "reference_reasoning": "This is a valid reference reasoning string."
    }
    recs_file.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    validator = DatasetValidator(dataset_dir=tmp_path)
    with pytest.raises(DatasetValidationError, match="not found in golden_resumes"):
        validator.validate_recommendations(recs_file, job_ids={"JOB_0001"}, resume_ids={"RES_0001"})


def test_validator_rejects_relevance_consistency_violation(tmp_path: Path):
    recs_file = tmp_path / "golden_recommendations.jsonl"
    rec = {
        "case_id": "MATCH_0001",
        "resume_id": "RES_0001",
        "job_id": "JOB_0001",
        "relevance": 3,
        "relevant_for_recommendation": False, # Violation! relevance=3 should have True
        "reference_reasoning": "This is a valid reference reasoning string."
    }
    recs_file.write_text(json.dumps(rec) + "\n", encoding="utf-8")
    validator = DatasetValidator(dataset_dir=tmp_path)
    with pytest.raises(DatasetValidationError, match="Consistency violation"):
        validator.validate_recommendations(recs_file, job_ids={"JOB_0001"}, resume_ids={"RES_0001"})


def test_validator_rejects_empty_dataset(tmp_path: Path):
    empty_file = tmp_path / "golden_jobs.jsonl"
    empty_file.write_text("", encoding="utf-8")
    validator = DatasetValidator(dataset_dir=tmp_path)
    with pytest.raises(DatasetValidationError, match="is empty"):
        validator.validate_jobs(empty_file)
