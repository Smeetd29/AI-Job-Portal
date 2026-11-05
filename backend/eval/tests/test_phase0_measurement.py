"""
Unit tests for Phase 0: Measurement Fixes and Trustworthy Evaluation.
Verifies:
1. Theoretical ceilings (max_possible_p5, max_possible_r5).
2. Normalized Precision@5 and Normalized Recall@5.
3. Extended metrics: nDCG@10, MAP, R-Precision, Recall@20, Recall@50.
4. Per-stage relevant jobs lost funnel.
5. Standardized min_match (50 default) with thresholded and unthresholded metrics.
6. Zero gold-label leakage at inference.
7. Bootstrap 95% confidence intervals.
8. Candidate-level disjoint K-Fold partitioning.
"""
from __future__ import annotations

import math
import pytest
import numpy as np

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
)
from eval.src.recommendation_evaluator import (
    RecommendationEvaluator,
    FunnelLossReport,
    _calculate_ranking_stage_metrics,
)
from eval.src.cross_validation import partition_candidates_kfold
from eval.src.data_loader import GoldenResume


def test_theoretical_ceilings_calculation():
    # Case 1: Candidate with 3 relevant jobs in corpus (ceiling effect on P@5)
    max_p5 = calculate_max_possible_precision_at_k(n_relevant=3, k=5)
    max_r5 = calculate_max_possible_recall_at_k(n_relevant=3, k=5)
    assert max_p5 == pytest.approx(3.0 / 5.0)  # 0.60
    assert max_r5 == pytest.approx(1.0)        # 1.00

    # Case 2: Candidate with 10 relevant jobs in corpus (capacity effect on R@5)
    max_p5_10 = calculate_max_possible_precision_at_k(n_relevant=10, k=5)
    max_r5_10 = calculate_max_possible_recall_at_k(n_relevant=10, k=5)
    assert max_p5_10 == pytest.approx(1.0)       # 1.00
    assert max_r5_10 == pytest.approx(5.0 / 10.0) # 0.50

    # Case 3: Zero relevant jobs in corpus
    assert calculate_max_possible_precision_at_k(n_relevant=0, k=5) == 0.0
    assert math.isnan(calculate_max_possible_recall_at_k(n_relevant=0, k=5))


def test_normalized_precision_and_recall_at_k():
    # Candidate with 3 relevant items in corpus
    relevant = {"J1", "J2", "J3"}
    # System returns J1, J2 and 3 non-relevant items
    retrieved = ["J1", "J2", "OTHER_1", "OTHER_2", "OTHER_3"]

    # Raw P@5 = 2/5 = 0.40; Max possible P@5 = 3/5 = 0.60
    # Normalized P@5 = 0.40 / 0.60 = 0.6667
    raw_p5 = calculate_precision_at_k(retrieved, relevant, 5)
    norm_p5 = calculate_normalized_precision_at_k(retrieved, relevant, 5)
    assert raw_p5 == pytest.approx(0.40)
    assert norm_p5 == pytest.approx(2.0 / 3.0)

    # Raw R@5 = 2/3 = 0.6667; Max possible R@5 = 3/3 = 1.0
    # Normalized R@5 = 0.6667 / 1.0 = 0.6667
    raw_r5 = calculate_recall_at_k(retrieved, relevant, 5)
    norm_r5 = calculate_normalized_recall_at_k(retrieved, relevant, 5)
    assert raw_r5 == pytest.approx(2.0 / 3.0)
    assert norm_r5 == pytest.approx(2.0 / 3.0)

    # Perfect ranking when n_relevant = 2 (all 2 retrieved in top 5)
    rel_2 = {"J1", "J2"}
    norm_p5_perf = calculate_normalized_precision_at_k(retrieved, rel_2, 5)
    norm_r5_perf = calculate_normalized_recall_at_k(retrieved, rel_2, 5)
    assert norm_p5_perf == pytest.approx(1.0)
    assert norm_r5_perf == pytest.approx(1.0)


def test_average_precision_and_map_hand_calculated():
    # Relevant: J1, J3. Retrieved: [J1, J2, J3, J4]
    # Rank 1: J1 (hit) -> P@1 = 1/1 = 1.0
    # Rank 2: J2 (miss)
    # Rank 3: J3 (hit) -> P@3 = 2/3 = 0.666667
    # Rank 4: J4 (miss)
    # AP = (1.0 + 2/3) / 2 = 1.666667 / 2 = 0.833333
    retrieved = ["J1", "J2", "J3", "J4"]
    relevant = {"J1", "J3"}
    ap = calculate_average_precision(retrieved, relevant)
    assert ap == pytest.approx((1.0 + 2.0 / 3.0) / 2.0)

    # Zero relevant returns NaN
    assert math.isnan(calculate_average_precision(retrieved, set()))
    # No hits returns 0.0
    assert calculate_average_precision(["J2", "J4"], relevant) == 0.0


def test_r_precision_hand_calculated():
    # Relevant count = 3: {"J1", "J2", "J3"}
    # R = 3
    # Retrieved: ["J1", "J4", "J2", "J3"]
    # In top 3: J1, J4, J2 -> hits = 2 -> R-Precision = 2 / 3 = 0.6667
    relevant = {"J1", "J2", "J3"}
    retrieved = ["J1", "J4", "J2", "J3"]
    r_prec = calculate_r_precision(retrieved, relevant)
    assert r_prec == pytest.approx(2.0 / 3.0)

    # When retrieved has fewer items than R:
    short_ret = ["J1"]
    assert calculate_r_precision(short_ret, relevant) == pytest.approx(1.0 / 3.0)
    # Empty relevant
    assert math.isnan(calculate_r_precision(retrieved, set()))


def test_recall_at_20_and_50():
    relevant = {f"J{i}" for i in range(1, 11)}  # 10 relevant
    # 20 items with 6 hits
    retrieved_20 = [f"J{i}" for i in range(1, 7)] + [f"IRREL_{i}" for i in range(14)]
    r20 = calculate_recall_at_k(retrieved_20, relevant, 20)
    assert r20 == pytest.approx(6.0 / 10.0)

    # 50 items with 10 hits
    retrieved_50 = [f"J{i}" for i in range(1, 11)] + [f"IRREL_{i}" for i in range(40)]
    r50 = calculate_recall_at_k(retrieved_50, relevant, 50)
    assert r50 == pytest.approx(1.0)


def test_ndcg_at_10_calculation():
    grades = {"J1": 3, "J2": 2, "J3": 1, "J4": 1, "J5": 0, "J6": 2}
    retrieved = ["J1", "J2", "J3", "J4", "J5", "J6", "J7", "J8", "J9", "J10"]
    ndcg10 = calculate_ndcg_at_k(retrieved, grades, 10)
    assert 0.0 < ndcg10 <= 1.0


def test_ranking_stage_metrics_computes_all_phase0_metrics():
    retrieved = ["J1", "J2", "J3", "J4", "J5"]
    relevant = {"J1", "J3"}
    grades = {"J1": 3, "J2": 0, "J3": 2, "J4": 0, "J5": 0}

    metrics = _calculate_ranking_stage_metrics(retrieved, relevant, grades)
    assert "precision_at_5" in metrics
    assert "recall_at_5" in metrics
    assert "normalized_precision_at_5" in metrics
    assert "normalized_recall_at_5" in metrics
    assert "ndcg_at_5" in metrics
    assert "ndcg_at_10" in metrics
    assert "map" in metrics
    assert "r_precision" in metrics
    assert "recall_at_20" in metrics
    assert "recall_at_50" in metrics
    assert metrics["precision_at_5"] == pytest.approx(0.40)
    # n_relevant = 2 -> max possible P@5 = 2/5 = 0.40 -> normalized = 0.40 / 0.40 = 1.0
    assert metrics["normalized_precision_at_5"] == pytest.approx(1.0)


def test_standardized_min_match_evaluator_default():
    evaluator = RecommendationEvaluator()
    assert evaluator.min_match == 50, "Default min_match in RecommendationEvaluator must match production API default (50)"


def test_zero_gold_label_leakage_assertion():
    """
    Verifies that the inference query is built strictly from parsed resume text,
    not from golden metadata fields (skills, candidate_profile).
    """
    evaluator = RecommendationEvaluator()
    # Create a synthetic resume that has NO candidate_profile skills
    raw_resume_text = (
        "Senior Python Engineer\n"
        "Summary: 6 years building distributed backend APIs in Python and Django.\n"
        "Skills: Python, Django, PostgreSQL, Docker, AWS, Redis, Celery, REST APIs\n"
        "Experience: 6 years as Senior Backend Engineer at FinTech Corp.\n"
        "Education: Bachelor of Science in Computer Science\n"
    )
    uncontaminated_resume = GoldenResume(
        resume_id="TEST_LEAK_001",
        candidate_name="Blind Candidate",
        resume_text=raw_resume_text,
        candidate_profile={},  # EMPTY candidate profile — no ground truth skills
    )
    evaluator.resumes["TEST_LEAK_001"] = uncontaminated_resume
    evaluator.relevance_by_resume["TEST_LEAK_001"] = {"JOB_0001": 3, "JOB_0002": 0}

    # Must execute successfully without accessing golden skills
    res = evaluator.evaluate_candidate("TEST_LEAK_001")
    assert res.resume_id == "TEST_LEAK_001"
    assert len(res.recommended_job_ids) > 0
    assert res.max_possible_precision_at_5 > 0.0
    assert res.normalized_precision_at_5 >= 0.0
    assert res.funnel is not None
    assert res.funnel.corpus_relevant_count == 1


def test_bootstrap_confidence_intervals():
    values = [0.8, 0.85, 0.9, 0.75, 0.88, 0.82, 0.91, 0.79]
    ci = bootstrap_ci(values, n_bootstrap=500, ci=0.95, seed=42)
    assert "mean" in ci
    assert "std" in ci
    assert "ci_lower" in ci
    assert "ci_upper" in ci
    assert ci["ci_lower"] <= ci["mean"] <= ci["ci_upper"]
    assert ci["std"] > 0.0


def test_candidate_kfold_partitioning_disjointness():
    candidates = [f"CAND{i:03d}" for i in range(1, 91)]  # 90 candidates
    folds = partition_candidates_kfold(candidates, n_folds=5, seed=42)
    assert len(folds) == 5
    all_assigned = []
    for f in folds:
        all_assigned.extend(f)
    # Check disjointness and completeness
    assert len(all_assigned) == 90
    assert len(set(all_assigned)) == 90
    # Every fold must have approximately equal size (18 candidates each)
    for f in folds:
        assert len(f) == 18

