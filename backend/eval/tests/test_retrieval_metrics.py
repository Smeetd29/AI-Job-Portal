from __future__ import annotations

import math
import pytest
from eval.src.retrieval_evaluator import (
    calculate_hit_rate_at_k,
    calculate_mrr,
    calculate_ndcg_at_k,
    calculate_precision_at_k,
    calculate_recall_at_k,
)


def test_precision_at_k_standard():
    retrieved = ["JOB_1", "JOB_2", "JOB_3", "JOB_4", "JOB_5"]
    relevant = {"JOB_1", "JOB_3"}
    # In top 5, 2 relevant -> 2 / 5 = 0.4
    assert calculate_precision_at_k(retrieved, relevant, 5) == 0.4
    # In top 3, 2 relevant -> 2 / 3 = 0.6666...
    assert round(calculate_precision_at_k(retrieved, relevant, 3), 4) == 0.6667


def test_precision_at_k_deduplication():
    # Multiple chunks from the same job must not count as multiple hits
    retrieved_with_duplicates = ["JOB_1", "JOB_1", "JOB_2", "JOB_2", "JOB_3"]
    relevant = {"JOB_1", "JOB_3"}
    # Deduplicated list: ["JOB_1", "JOB_2", "JOB_3"]
    # Top 2: ["JOB_1", "JOB_2"] -> 1 hit / 2 = 0.5
    assert calculate_precision_at_k(retrieved_with_duplicates, relevant, 2) == 0.5
    # Top 3: ["JOB_1", "JOB_2", "JOB_3"] -> 2 hits / 3 = 0.6667
    assert round(calculate_precision_at_k(retrieved_with_duplicates, relevant, 3), 4) == 0.6667


def test_precision_at_k_edge_cases():
    assert calculate_precision_at_k([], {"JOB_1"}, 5) == 0.0
    assert calculate_precision_at_k(["JOB_1"], {"JOB_1"}, 0) == 0.0
    # Fewer than K retrieved
    assert calculate_precision_at_k(["JOB_1"], {"JOB_1"}, 5) == 0.2


def test_recall_at_k_standard():
    retrieved = ["JOB_1", "JOB_2", "JOB_3", "JOB_4", "JOB_5"]
    relevant = {"JOB_1", "JOB_3", "JOB_9", "JOB_10"}  # 4 total relevant in corpus
    # In top 5, retrieved 2 out of 4 -> 2 / 4 = 0.5
    assert calculate_recall_at_k(retrieved, relevant, 5) == 0.5
    # In top 3, retrieved 2 out of 4 -> 2 / 4 = 0.5
    assert calculate_recall_at_k(retrieved, relevant, 3) == 0.5
    # In top 1, retrieved 1 out of 4 -> 1 / 4 = 0.25
    assert calculate_recall_at_k(retrieved, relevant, 1) == 0.25


def test_recall_at_k_deduplication():
    # Duplicate chunks from JOB_1 must not inflate recall count
    retrieved = ["JOB_1", "JOB_1", "JOB_1", "JOB_2"]
    relevant = {"JOB_1", "JOB_9"}  # 2 total relevant
    # Top 2 deduped: ["JOB_1", "JOB_2"] -> 1 hit / 2 = 0.5
    assert calculate_recall_at_k(retrieved, relevant, 2) == 0.5


def test_recall_at_k_zero_relevant_in_corpus():
    # Documented policy: When corpus has 0 relevant items, recall is undefined (NaN)
    assert math.isnan(calculate_recall_at_k([], set(), 5))
    assert math.isnan(calculate_recall_at_k(["JOB_1"], set(), 5))


def test_hit_rate_at_k():
    retrieved = ["JOB_1", "JOB_2", "JOB_3"]
    assert calculate_hit_rate_at_k(retrieved, {"JOB_2"}, 3) == 1.0
    assert calculate_hit_rate_at_k(retrieved, {"JOB_9"}, 3) == 0.0
    assert calculate_hit_rate_at_k(retrieved, {"JOB_3"}, 2) == 0.0  # JOB_3 is at rank 3


def test_mrr_calculation():
    # Relevant item at rank 1 -> 1.0
    assert calculate_mrr(["JOB_1", "JOB_2"], {"JOB_1"}) == 1.0
    # Relevant item at rank 2 -> 0.5
    assert calculate_mrr(["JOB_1", "JOB_2"], {"JOB_2"}) == 0.5
    # Relevant item at rank 4 -> 0.25
    assert calculate_mrr(["JOB_1", "JOB_2", "JOB_3", "JOB_4"], {"JOB_4"}) == 0.25
    # Duplicate item at rank 1 and 2: rank of first occurrence is 1 -> 1.0
    assert calculate_mrr(["JOB_1", "JOB_1", "JOB_2"], {"JOB_1"}) == 1.0
    # No relevant item -> 0.0
    assert calculate_mrr(["JOB_1", "JOB_2"], {"JOB_99"}) == 0.0


def test_ndcg_at_k_hand_calculated():
    """
    Mathematical Proof by Hand:
    retrieved = ["J1", "J2", "J3", "J4"]
    grades = {"J1": 3, "J2": 0, "J3": 2, "J4": 1}
    k = 3

    DCG@3:
      rank 1 (J1, rel=3): gain = (2^3 - 1) = 7, discount = log2(1+1) = 1.0 -> 7.0
      rank 2 (J2, rel=0): gain = (2^0 - 1) = 0, discount = log2(2+1) -> 0.0
      rank 3 (J3, rel=2): gain = (2^2 - 1) = 3, discount = log2(3+1) = 2.0 -> 1.5
      Total DCG@3 = 7.0 + 0.0 + 1.5 = 8.500000

    IDCG@3:
      Sorted corpus grades: [3, 2, 1, 0]
      rank 1 (rel=3): 7 / log2(2) = 7.0
      rank 2 (rel=2): 3 / log2(3) = 3 / 1.584962500721156 = 1.8927892607143721
      rank 3 (rel=1): 1 / log2(4) = 1 / 2.0 = 0.5
      Total IDCG@3 = 7.0 + 1.8927892607143721 + 0.5 = 9.392789260714373

    Expected nDCG@3 = 8.5 / 9.392789260714373 = 0.90494951... -> 0.9049
    """
    grades = {"J1": 3, "J2": 0, "J3": 2, "J4": 1}
    retrieved = ["J1", "J2", "J3", "J4"]
    ndcg3 = calculate_ndcg_at_k(retrieved, grades, 3)
    assert round(ndcg3, 4) == 0.9049


def test_ndcg_at_k_perfect_ranking():
    grades = {"JOB_1": 3, "JOB_2": 2, "JOB_3": 1}
    # Perfect ranking must be exactly 1.0
    assert round(calculate_ndcg_at_k(["JOB_1", "JOB_2", "JOB_3"], grades, 3), 4) == 1.0


def test_ndcg_at_k_edge_cases():
    grades = {"JOB_1": 3, "JOB_2": 2}
    assert calculate_ndcg_at_k([], grades, 3) == 0.0
    assert calculate_ndcg_at_k(["JOB_X", "JOB_Y"], grades, 2) == 0.0
    # Zero positive grades in corpus
    assert math.isnan(calculate_ndcg_at_k(["JOB_X"], {"JOB_X": 0}, 1))


def test_micro_vs_macro_aggregation():
    # Query 1: 2 hits out of 5 slots, 2 known relevant in corpus
    q1_retrieved = ["J1", "J2", "J3", "J4", "J5"]
    q1_relevant = {"J1", "J2"}
    p_q1 = calculate_precision_at_k(q1_retrieved, q1_relevant, 5)  # 2/5 = 0.4
    r_q1 = calculate_recall_at_k(q1_retrieved, q1_relevant, 5)     # 2/2 = 1.0

    # Query 2: 4 hits out of 5 slots, 8 known relevant in corpus
    q2_retrieved = ["J6", "J7", "J8", "J9", "J10"]
    q2_relevant = {"J6", "J7", "J8", "J9", "J11", "J12", "J13", "J14"}
    p_q2 = calculate_precision_at_k(q2_retrieved, q2_relevant, 5)  # 4/5 = 0.8
    r_q2 = calculate_recall_at_k(q2_retrieved, q2_relevant, 5)     # 4/8 = 0.5

    # Macro Precision@5 = (0.4 + 0.8) / 2 = 0.6000
    macro_p5 = (p_q1 + p_q2) / 2.0
    assert macro_p5 == pytest.approx(0.6000)

    # Micro Precision@5 = (2 + 4) / (5 + 5) = 6 / 10 = 0.6000
    # Note: With fixed K denominator across all queries, Macro P@K == Micro P@K
    micro_p5 = (2 + 4) / 10.0
    assert micro_p5 == pytest.approx(0.6000)

    # Macro Recall@5 = (1.0 + 0.5) / 2 = 0.7500
    macro_r5 = (r_q1 + r_q2) / 2.0
    assert macro_r5 == pytest.approx(0.7500)

    # Micro Recall@5 = (2 + 4) / (2 + 8) = 6 / 10 = 0.6000
    # Micro Recall weights by candidate corpus relevance, revealing true aggregate coverage
    micro_r5 = (2 + 4) / (2 + 8)
    assert micro_r5 == pytest.approx(0.6000)
    assert macro_r5 != micro_r5


def test_fixed_k_denominator_under_short_retrieval():
    # If system returns only 2 items due to strict thresholding:
    retrieved = ["J1", "J2"]
    relevant = {"J1", "J2"}
    # Precision@5 uses fixed K=5 denominator (standard TREC convention)
    # Empty slots count as false negatives for rank K
    assert calculate_precision_at_k(retrieved, relevant, 5) == 0.4  # 2 / 5, not 2 / 2


def test_unjudged_items_treated_as_irrelevant():
    retrieved = ["J1", "J_UNJUDGED", "J2"]
    relevant = {"J1", "J2"}
    # J_UNJUDGED is not in relevant set, so it counts as non-relevant
    assert calculate_precision_at_k(retrieved, relevant, 3) == 2.0 / 3.0
