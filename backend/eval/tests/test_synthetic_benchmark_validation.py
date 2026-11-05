from __future__ import annotations

import csv
import json
import pytest
from pathlib import Path
from eval.src.data_loader import SyntheticBenchmarkLoader
from eval.src.dataset_validation import SyntheticBenchmarkValidator, DatasetValidationError


def test_production_synthetic_benchmark_passes_validation():
    validator = SyntheticBenchmarkValidator()
    results = validator.validate_all()
    assert results["jobs_count"] == 200
    assert results["candidates_count"] == 60
    assert results["judgments_count"] == 12000
    assert results["split_counts"]["train"] == 42
    assert results["split_counts"]["validation"] == 6
    assert results["split_counts"]["test"] == 12
    # Verify grade distribution
    assert sum(results["grade_distribution"].values()) == 12000
    assert results["grade_distribution"][0] == 9355
    assert results["grade_distribution"][1] == 1297
    assert results["grade_distribution"][2] == 895
    assert results["grade_distribution"][3] == 453


def test_synthetic_data_loader_interface():
    loader = SyntheticBenchmarkLoader()
    jobs = loader.load_jobs()
    resumes = loader.load_resumes()
    recs = loader.load_recommendations()
    splits = loader.load_splits()

    assert len(jobs) == 200
    assert len(resumes) == 60
    assert len(recs) == 12000
    assert len(splits) == 60

    # Test split candidate getters
    train_cands = loader.get_candidates_for_split("train")
    val_cands = loader.get_candidates_for_split("validation")
    test_cands = loader.get_candidates_for_split("test")

    assert len(train_cands) == 42
    assert len(val_cands) == 6
    assert len(test_cands) == 12

    # Zero leakage
    assert len(train_cands & val_cands) == 0
    assert len(train_cands & test_cands) == 0
    assert len(val_cands & test_cands) == 0

    # Hashes
    hashes = loader.compute_split_hashes()
    assert "candidate_level_splits_sha256" in hashes
    assert len(hashes["candidate_level_splits_sha256"]) == 64


def test_validator_rejects_split_leakage(tmp_path):
    validator = SyntheticBenchmarkValidator()
    cand_ids = {f"CAND{i:03d}" for i in range(1, 61)}

    # Create a corrupted split file where CAND001 is in both train and test
    split_file = tmp_path / "candidate_level_splits.csv"
    with open(split_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "split"])
        for i in range(1, 43):
            writer.writerow([f"CAND{i:03d}", "train"])
        for i in range(43, 49):
            writer.writerow([f"CAND{i:03d}", "validation"])
        for i in range(49, 61):
            writer.writerow([f"CAND{i:03d}", "test"])
        # Leak CAND001 into test
        writer.writerow(["CAND001", "test"])

    with pytest.raises(DatasetValidationError, match="Data leakage|Duplicate candidate"):
        validator.validate_splits(split_file, cand_ids)


def test_validator_rejects_invalid_relevance_grade(tmp_path):
    validator = SyntheticBenchmarkValidator()
    cand_ids = {"CAND001"}
    job_ids = {"JOB001"}

    judgments_file = tmp_path / "synthetic_relevance_judgments.csv"
    with open(judgments_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "job_id", "relevance_grade"])
        writer.writerow(["CAND001", "JOB001", "5"])  # Invalid: grade > 3

    with pytest.raises(DatasetValidationError, match="Invalid relevance_grade"):
        validator.validate_judgments(judgments_file, job_ids, cand_ids)


def test_validator_rejects_unknown_job_reference(tmp_path):
    validator = SyntheticBenchmarkValidator()
    cand_ids = {"CAND001"}
    job_ids = {"JOB001"}

    judgments_file = tmp_path / "synthetic_relevance_judgments.csv"
    with open(judgments_file, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "job_id", "relevance_grade"])
        writer.writerow(["CAND001", "JOB999", "2"])  # JOB999 not in job_ids

    with pytest.raises(DatasetValidationError, match="Unknown job_id"):
        validator.validate_judgments(judgments_file, job_ids, cand_ids)

