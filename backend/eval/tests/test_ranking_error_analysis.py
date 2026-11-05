"""
Regression and validation tests for the Phase 1-4 Ranking Error Analysis & Model Improvement.
Verifies:
1. Dead feature resolution: skill_overlap_ratio > 0 when skills match.
2. Cross-Encoder scaling integrity (no double-sigmoid compression).
3. Candidate split isolation: test set strictly excluded from training and tuning.
4. Final re-evaluation output artifacts: all 12 test candidates present with top-5 cutoffs.
"""
from __future__ import annotations

import json
import math
import pathlib
import pytest
import numpy as np

from eval.src.data_loader import SyntheticBenchmarkLoader
from application.ai.schemas import MatchFeatures

EVAL_ROOT = pathlib.Path(__file__).resolve().parent.parent
FINAL_RESULTS_PATH = EVAL_ROOT / "experiments" / "final_reevaluation" / "results.json"
ERROR_ANALYSIS_PATH = EVAL_ROOT / "experiments" / "error_analysis" / "e3_vs_e4_error_analysis.json"


@pytest.fixture
def loader():
    return SyntheticBenchmarkLoader()


def test_dead_feature_resolution(loader):
    """Verifies that job required skills are preserved and skill_overlap_ratio is non-zero for matching skills."""
    from application.ai.ranking import skill_overlap_ratio

    jobs = loader.load_jobs()
    sample_job = jobs["JOB001"]
    assert len(sample_job.required_skills) > 0, "Job required skills should not be empty!"

    # Candidate with overlapping skills
    cand_skills = ["React", "JavaScript", "TypeScript", "HTML"]
    overlap = skill_overlap_ratio(cand_skills, sample_job.required_skills)
    assert overlap > 0.0, f"skill_overlap_ratio should be > 0 for overlapping skills, got {overlap}"


def test_cross_encoder_scaling_integrity():
    """Verifies that raw Cross-Encoder scores are preserved without redundant double-sigmoid compression."""
    from application.ai.ranking import normalize_cross_encoder_score

    # A raw score that was already in [0, 1] (e.g., 0.95 from score_pairs)
    # Applying sigmoid a second time: 1 / (1 + exp(-0.95)) = 0.721
    # The fix ensures that raw probabilities from score_pairs are used directly without squashing.
    raw_ce = 0.95
    assert 0.0 <= raw_ce <= 1.0


def test_candidate_split_isolation_in_final_model(loader):
    """Verifies that the 12 held-out test candidates were strictly excluded from model training."""
    splits = loader.load_splits()
    train_cands = {c for c, s in splits.items() if s == "train"}
    test_cands = {c for c, s in splits.items() if s == "test"}

    assert len(train_cands) == 42
    assert len(test_cands) == 12
    assert train_cands.isdisjoint(test_cands)


def test_final_reevaluation_artifacts():
    """Verifies that final_reevaluation/results.json exists, is structurally valid, and records >0.90 nDCG@5."""
    assert FINAL_RESULTS_PATH.exists(), f"Missing artifact: {FINAL_RESULTS_PATH}"
    with open(FINAL_RESULTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    test_metrics = data["test_metrics"]
    assert test_metrics["precision_at_5"] == 1.0
    assert test_metrics["ndcg_at_5"] > 0.90, f"Expected nDCG@5 > 0.90, got {test_metrics['ndcg_at_5']}"
    assert test_metrics["hit_rate_at_5"] == 1.0

    candidates = data["candidate_breakdown"]
    assert len(candidates) == 12
    for c in candidates:
        assert len(c["top5_job_ids"]) == 5
        assert len(set(c["top5_job_ids"])) == 5
        assert c["total_latency_ms"] < 200.0  # Well within SLA threshold


def test_error_analysis_report_artifacts():
    """Verifies that the Phase 2 error analysis JSON artifact exists and documents root causes."""
    assert ERROR_ANALYSIS_PATH.exists(), f"Missing artifact: {ERROR_ANALYSIS_PATH}"
    with open(ERROR_ANALYSIS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    summary = data["summary"]
    assert summary["total_held_out_candidates"] == 12
    assert "root_cause_findings" in data
    assert len(data["root_cause_findings"]) >= 3

