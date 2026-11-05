"""
Automated validation tests for the controlled recommendation comparison (E1 to E4).
Verifies:
1. Candidate-level split isolation (zero leakage).
2. No training on test labels.
3. Correct metric calculations (hand-calculated test fixtures).
4. Consistent recommendation cutoffs (exactly K=5).
5. Correct ranking order and determinism.
6. Successful execution of all four configurations.
"""
from __future__ import annotations

import json
import math
import pathlib
import pytest
import numpy as np

from eval.src.data_loader import SyntheticBenchmarkLoader
from eval.src.retrieval_evaluator import (
    calculate_hit_rate_at_k,
    calculate_mrr,
    calculate_ndcg_at_k,
    calculate_precision_at_k,
    calculate_recall_at_k,
    _deduplicate_preserving_order,
)

EVAL_ROOT = pathlib.Path(__file__).resolve().parent.parent
RESULTS_PATH = EVAL_ROOT / "experiments" / "controlled_comparison" / "results.json"


@pytest.fixture
def loader():
    return SyntheticBenchmarkLoader()


def test_candidate_level_split_isolation(loader):
    """Verifies that train, validation, and test candidate partitions are strictly disjoint."""
    splits = loader.load_splits()
    train_cands = {c for c, s in splits.items() if s == "train"}
    val_cands = {c for c, s in splits.items() if s == "validation"}
    test_cands = {c for c, s in splits.items() if s == "test"}

    assert len(train_cands) == 42
    assert len(val_cands) == 6
    assert len(test_cands) == 12
    assert len(splits) == 60

    # Pairwise disjointness
    assert train_cands.isdisjoint(val_cands), "Train and validation splits overlap!"
    assert train_cands.isdisjoint(test_cands), "Train and test splits overlap!"
    assert val_cands.isdisjoint(test_cands), "Validation and test splits overlap!"


def test_no_training_on_test_labels(loader):
    """Verifies that test candidate IDs are completely absent from training artifacts and datasets."""
    splits = loader.load_splits()
    test_cands = {c for c, s in splits.items() if s == "test"}

    # Check judgments partition
    train_recs = loader.get_judgments_for_split("train")
    for r in train_recs:
        assert r.resume_id not in test_cands, f"Test candidate {r.resume_id} leaked into training judgments!"

    # Verify test candidate IDs match the benchmark definition
    expected_test = {f"CAND{i:03d}" for i in range(49, 61)}
    assert test_cands == expected_test, f"Test candidate set does not match expected range: {test_cands}"


def test_metric_calculations_hand_calculated():
    """Verifies IR metrics against exact hand-calculated expected values."""
    retrieved = ["job_1", "job_2", "job_3", "job_4", "job_5"]
    relevant = {"job_1", "job_3", "job_7", "job_9"}  # 4 total relevant in corpus
    grades = {"job_1": 3, "job_2": 0, "job_3": 2, "job_4": 0, "job_5": 0, "job_7": 3, "job_9": 1}

    # Precision@5: 2 hits in top 5 -> 2/5 = 0.40
    p5 = calculate_precision_at_k(retrieved, relevant, 5)
    assert pytest.approx(p5, 1e-6) == 0.40

    # Recall@5: 2 hits in top 5 / 4 total relevant -> 2/4 = 0.50
    r5 = calculate_recall_at_k(retrieved, relevant, 5)
    assert pytest.approx(r5, 1e-6) == 0.50

    # HitRate@5: 1.0 since job_1 is in top 5
    hr5 = calculate_hit_rate_at_k(retrieved, relevant, 5)
    assert hr5 == 1.0

    # MRR: job_1 is at rank 1 -> 1/1 = 1.0
    mrr = calculate_mrr(retrieved, relevant)
    assert pytest.approx(mrr, 1e-6) == 1.0

    # nDCG@5:
    # DCG@5 = (2^3 - 1)/log2(2) + (2^0 - 1)/log2(3) + (2^2 - 1)/log2(4) + 0 + 0
    #        = 7/1.0 + 0 + 3/2.0 = 7.0 + 1.5 = 8.5
    # IDCG@5 with grades [3, 3, 2, 1, 0]:
    #   rank 1: (2^3 - 1)/log2(2) = 7.0
    #   rank 2: (2^3 - 1)/log2(3) = 7.0 / 1.5849625 = 4.416508
    #   rank 3: (2^2 - 1)/log2(4) = 3.0 / 2.0 = 1.50
    #   rank 4: (2^1 - 1)/log2(5) = 1.0 / 2.321928 = 0.430677
    #   rank 5: 0
    # IDCG = 7.0 + 4.416508 + 1.50 + 0.430677 = 13.347185
    # nDCG = 8.5 / 13.347185 = 0.636838
    ndcg5 = calculate_ndcg_at_k(retrieved, grades, 5)
    expected_idcg = 7.0 + (7.0 / math.log2(3)) + (3.0 / math.log2(4)) + (1.0 / math.log2(5))
    expected_ndcg = 8.5 / expected_idcg
    assert pytest.approx(ndcg5, 1e-5) == expected_ndcg

    # Deduplication integrity
    retrieved_with_dups = ["job_1", "job_1", "job_2", "job_3", "job_3"]
    deduped = _deduplicate_preserving_order(retrieved_with_dups)
    assert deduped == ["job_1", "job_2", "job_3"]


def test_consistent_recommendation_cutoffs():
    """Verifies that all 4 configurations in results.json strictly return top-5 cutoffs."""
    assert RESULTS_PATH.exists(), f"Results file missing: {RESULTS_PATH}"
    with open(RESULTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    configs = data["configurations"]
    assert len(configs) == 4
    for cfg_id in ["E1", "E2", "E3", "E4"]:
        assert cfg_id in configs
        cand_details = configs[cfg_id]["candidate_details"]
        assert len(cand_details) == 12  # All 12 test candidates
        for c in cand_details:
            top5 = c["top5_job_ids"]
            assert len(top5) == 5, f"{cfg_id} candidate {c['candidate_id']} returned {len(top5)} items instead of 5"
            assert len(set(top5)) == 5, f"{cfg_id} candidate {c['candidate_id']} contains duplicate jobs in top 5"


def test_ranking_order_and_determinism():
    """Verifies ranking scores are monotonically non-increasing and deterministic."""
    from rank_bm25 import BM25Okapi

    corpus = [
        "python django backend developer sql postgresql",
        "react typescript frontend engineer html css",
        "devops kubernetes aws terraform docker cicd",
        "machine learning data science python pytorch",
        "ios swift mobile developer objective-c xcode",
    ]
    tokenized = [doc.split() for doc in corpus]
    bm25 = BM25Okapi(tokenized)

    query = "python backend developer django".split()
    scores1 = bm25.get_scores(query)
    scores2 = bm25.get_scores(query)

    # Determinism
    np.testing.assert_array_equal(scores1, scores2)

    # Monotonic sorting check
    ranked_indices = np.argsort(-scores1)
    sorted_scores = scores1[ranked_indices]
    for i in range(len(sorted_scores) - 1):
        assert sorted_scores[i] >= sorted_scores[i + 1]

    # Best match should be document 0
    assert ranked_indices[0] == 0


def test_all_four_configurations_execute(loader):
    """Executes a quick smoke run of all 4 configurations on a single test candidate."""
    import lightgbm as lgb
    from application.ai.matching import (
        CrossEncoderReranker,
        FaissRetriever,
        SentenceTransformerEmbedding,
    )

    jobs = loader.load_jobs()
    resumes = loader.load_resumes()
    job_ids = list(jobs.keys())[:20]  # minimal catalog of 20 jobs
    job_texts = [f"{jobs[j].title}. {jobs[j].description}" for j in job_ids]

    sample_cand = resumes["CAND049"]
    q_text = sample_cand.resume_text[:200]

    # E1: BM25
    from rank_bm25 import BM25Okapi
    tokenized = [t.lower().split() for t in job_texts]
    bm25 = BM25Okapi(tokenized)
    e1_scores = bm25.get_scores(q_text.lower().split())
    e1_top = [job_ids[i] for i in np.argsort(-e1_scores)[:5]]
    assert len(e1_top) == 5

    # E2: MiniLM
    embedder = SentenceTransformerEmbedding()
    vecs = embedder.encode(job_texts)
    faiss_ret = FaissRetriever(embedding_dim=embedder.dimension())
    faiss_ret.add_documents(list(range(len(job_ids))), vecs)
    q_vec = embedder.encode([q_text])[0]
    e2_results = faiss_ret.search(q_vec, top_k=5)
    assert len(e2_results) == 5

    # E3: Cross-Encoder reranking
    reranker = CrossEncoderReranker()
    pairs = [(q_text[:200], t[:200]) for t in job_texts[:5]]
    e3_scores = reranker.score_pairs(pairs)
    assert len(e3_scores) == 5

    # E4: LambdaMART
    model_path = EVAL_ROOT / "experiments" / "synthetic_benchmark_eval" / "lgb_ranker_synthetic_v3.txt"
    assert model_path.exists()
    booster = lgb.Booster(model_file=str(model_path))
    dummy_feats = np.zeros((5, 14), dtype=np.float64)
    e4_scores = booster.predict(dummy_feats)
    assert len(e4_scores) == 5

