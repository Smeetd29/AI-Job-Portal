from __future__ import annotations

import pytest
from eval.src.data_loader import GoldenDataLoader
from eval.src.recommendation_evaluator import (
    RecommendationEvaluator,
    _calculate_ranking_stage_metrics,
)


def test_ranking_stage_metrics_match_hand_calculated_example():
    result = _calculate_ranking_stage_metrics(
        ["irrelevant", "relevant-first", "relevant-second", "other", "other-two"],
        {"relevant-first", "relevant-second"},
        {"irrelevant": 0, "relevant-first": 3, "relevant-second": 2},
    )

    assert result["precision_at_5"] == pytest.approx(0.4)
    assert result["recall_at_5"] == pytest.approx(1.0)
    assert result["hit_rate_at_5"] == 1.0
    assert result["mrr"] == pytest.approx(0.5)
    assert 0.0 < result["ndcg_at_5"] < 1.0


def test_recommendation_evaluator_runs_on_candidate():
    loader = GoldenDataLoader()
    evaluator = RecommendationEvaluator(loader=loader)

    # Evaluate candidate RES_0001 (Lena Silva: Security Intern)
    res = evaluator.evaluate_candidate("RES_0001")
    assert res.resume_id == "RES_0001"
    assert len(res.recommended_job_ids) > 0
    # Relevant Security Analyst Intern job (JOB_0043) should be recommended near the top
    assert "JOB_0043" in res.recommended_job_ids[:5]
    # No duplicate recommendations
    assert res.duplicate_count == 0
    # Pipeline stages must be traced
    assert len(res.stages.raw_retrieved_ids) > 0
    assert len(res.stages.reranked_ids) > 0
    assert len(res.stages.scored_ids) > 0
    # Precision@5 and Recall@5 must be defined in [0, 1]
    assert 0.0 <= res.precision_at_5 <= 1.0
    assert 0.0 <= res.recall_at_5 <= 1.0
    assert 0.0 <= res.ndcg_at_5 <= 1.0


def test_recommendation_evaluator_filters_ineligible_jobs():
    loader = GoldenDataLoader()
    evaluator = RecommendationEvaluator(loader=loader, min_match=60)
    res = evaluator.evaluate_candidate("RES_0002")
    assert len(res.recommended_job_ids) == 5
    for s in res.match_scores:
        assert s >= 60

    # Verify fallback ensures 5 recommendations even when threshold exceeds all match scores
    evaluator_high = RecommendationEvaluator(loader=loader, min_match=95)
    res_fallback = evaluator_high.evaluate_candidate("RES_0001")
    assert len(res_fallback.recommended_job_ids) == 5


def test_hard_negatives_omitted_or_ranked_low():
    loader = GoldenDataLoader()
    evaluator = RecommendationEvaluator(loader=loader)
    # RES_0001 is an intern; JOB_0025 is Lead Security Analyst (requires 8+ yrs, Lead level, hard negative)
    res = evaluator.evaluate_candidate("RES_0001")
    # Lead job must not be in the top 3 recommendations for an intern
    assert "JOB_0025" not in res.recommended_job_ids[:3]
