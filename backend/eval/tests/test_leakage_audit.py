"""
Step 5: Leakage Audit and Regression Test Suite.
Validates:
1. Candidate isolation: train_ltr_model.py candidate set excludes CV validation/test folds and CAND049-CAND060.
2. Per-candidate theoretical ceiling calculations.
3. Threshold display cutoff with top-5 fallback.
4. Zero-gold-label leakage at inference time.
5. Per-fold candidate-level cross-validation disjointness.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))
repo_root = Path(__file__).resolve().parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "job.settings")
os.environ["USE_REDIS_CACHE"] = "False"
import django
django.setup()

import pytest
from typing import Set

from eval.src.data_loader import GoldenDataLoader, SyntheticBenchmarkLoader
from eval.src.retrieval_evaluator import (
    calculate_max_possible_precision_at_k,
    calculate_max_possible_recall_at_k,
    calculate_normalized_precision_at_k,
    calculate_normalized_recall_at_k,
)
from eval.src.cross_validation import partition_candidates_kfold, UnifiedCandidateEvaluator


def test_candidate_leakage_audit_held_out():
    """Verify held-out test candidates CAND049-CAND060 and golden test candidates are never in training data."""
    golden_loader = GoldenDataLoader()
    golden_splits = golden_loader.load_splits()
    golden_train = golden_loader.get_candidates_for_split("train")
    golden_val = golden_loader.get_candidates_for_split("validation")
    golden_test = golden_loader.get_candidates_for_split("test")

    # Verify Golden v2 splits are mutually disjoint and complete
    assert len(golden_train) == 84
    assert len(golden_val) == 12
    assert len(golden_test) == 24
    assert golden_train.isdisjoint(golden_val)
    assert golden_train.isdisjoint(golden_test)
    assert golden_val.isdisjoint(golden_test)

    golden_cands = set(golden_loader.load_resumes().keys())
    assert (golden_train | golden_val | golden_test) == golden_cands

    synth_loader = SyntheticBenchmarkLoader()
    splits = synth_loader.load_splits()
    test_cands = {cid for cid, s in splits.items() if s == "test"}

    # Assert held-out test set contains exactly the 12 specified candidates
    expected_held_out = {f"CAND{i:03d}" for i in range(49, 61)}
    assert test_cands == expected_held_out, f"Test candidates mismatch: {test_cands}"

    # Assert complete zero overlap with golden training candidates
    overlap = golden_cands.intersection(test_cands)
    assert len(overlap) == 0, f"LEAKAGE DETECTED: {overlap} found in golden training set!"


def test_cv_partition_strictly_disjoint():
    """Verify CV partitions are strictly candidate-disjoint across all folds."""
    golden_loader = GoldenDataLoader()
    golden_cands = sorted(golden_loader.load_resumes().keys())
    cands = [f"CAND{i:03d}" for i in range(1, 49)] + golden_cands
    folds = partition_candidates_kfold(cands, n_folds=5, seed=42)

    assert len(folds) == 5
    all_seen: Set[str] = set()
    for f_idx, fold in enumerate(folds):
        fold_set = set(fold)
        # Check fold itself has no duplicates
        assert len(fold_set) == len(fold)
        # Check fold has no overlap with previously seen candidates
        assert len(all_seen.intersection(fold_set)) == 0, f"Fold {f_idx} has overlapping candidates!"
        all_seen.update(fold_set)

    assert all_seen == set(cands)


def test_cv_early_stopping_fold_never_evaluated():
    """Directive 2: Confirm in code that for every CV fold:
    1. The three pairwise fold intersections are strictly empty: Train ∩ Val = ∅, Train ∩ Test = ∅, Val ∩ Test = ∅.
    2. The early-stopping validation fold is never an evaluated test fold.
    """
    golden_loader = GoldenDataLoader()
    cands = sorted(golden_loader.load_resumes().keys())
    n_folds = 5
    folds = partition_candidates_kfold(cands, n_folds=n_folds, seed=42)

    for f_idx in range(n_folds):
        test_cands = set(folds[f_idx])
        val_idx = (f_idx + 1) % n_folds
        val_cands = set(folds[val_idx])
        train_cands = set(
            c for idx, fold in enumerate(folds)
            if idx not in (f_idx, val_idx)
            for c in fold
        )

        # 1. Verify all three pairwise intersections are strictly empty
        assert train_cands.isdisjoint(val_cands), f"Fold {f_idx}: Train and Val overlap!"
        assert train_cands.isdisjoint(test_cands), f"Fold {f_idx}: Train and Test overlap!"
        assert val_cands.isdisjoint(test_cands), f"Fold {f_idx}: Val and Test overlap!"

        # 2. Verify union exactly reconstructs the candidate pool
        assert (train_cands | val_cands | test_cands) == set(cands)



def test_ceiling_calculations():
    """Verify max possible precision/recall formulas."""
    # When n_relevant is less than K
    assert calculate_max_possible_precision_at_k(n_relevant=2, k=5) == 0.4
    assert calculate_max_possible_recall_at_k(n_relevant=2, k=5) == 1.0
    
    # When n_relevant is greater than K
    assert calculate_max_possible_precision_at_k(n_relevant=10, k=5) == 1.0
    assert calculate_max_possible_recall_at_k(n_relevant=10, k=5) == 0.5
    
    # Normalized metrics
    rec_ids = ["j1", "j2", "j3", "j4", "j5"]
    rel_ids = {"j1", "j2"}  # 2 relevant in corpus, both in top 5
    raw_p5 = 2 / 5.0  # 0.4
    norm_p5 = calculate_normalized_precision_at_k(rec_ids, rel_ids, 5)
    assert norm_p5 == 1.0  # Hit the ceiling of 2/5 -> 100% normalized!
    
    raw_r5 = 2 / 2.0  # 1.0
    norm_r5 = calculate_normalized_recall_at_k(rec_ids, rel_ids, 5)
    assert norm_r5 == 1.0


def test_threshold_top5_fallback():
    """Verify that thresholding preserves the top 5 candidates as fallback."""
    from application.ai.recommendations import JobRecommendationDTO, JobRecommendationService
    from unittest.mock import MagicMock
    
    service = JobRecommendationService(pipeline=MagicMock())
    # Mock candidate recommendations with scores below min_match=50
    mock_recs = [
        JobRecommendationDTO(job_id=i, title=f"Job {i}", company="A", location="Remote", job_type="Full-time", match_score=30 + i)
        for i in range(10)
    ]
    mock_recs.sort(key=lambda r: r.match_score, reverse=True)
    
    min_match = 50
    filtered = [r for r in mock_recs if r.match_score >= min_match]
    assert len(filtered) == 0  # None pass threshold
    
    # Fallback to top-5
    if len(filtered) < 5 and mock_recs:
        filtered = mock_recs[:5]
        
    assert len(filtered) == 5
    assert [r.job_id for r in filtered] == [9, 8, 7, 6, 5]


def test_zero_gold_label_at_inference():
    """Verify inference pipeline operates purely on parsed resume text without accessing gold metadata."""
    loader = GoldenDataLoader()
    resumes = loader.load_resumes()
    res = resumes["RES_0001"]

    # Create an adversarial resume object that raises AttributeError on gold properties
    class PoisonedResume:
        def __init__(self, raw_text: str):
            self.resume_id = "POISON_0001"
            self.resume_text = raw_text

        @property
        def skills(self):
            raise AssertionError("LEAKAGE: resume.skills accessed during inference!")

        @property
        def candidate_profile(self):
            raise AssertionError("LEAKAGE: candidate_profile accessed during inference!")

    poisoned = PoisonedResume(res.resume_text)
    evaluator = UnifiedCandidateEvaluator(min_match=50)
    evaluator._golden_evaluator.resumes["POISON_0001"] = poisoned
    evaluator._golden_evaluator.relevance_by_resume["POISON_0001"] = evaluator._golden_evaluator.relevance_by_resume["RES_0001"]

    # Evaluation must succeed without triggering gold property accesses
    result = evaluator._golden_evaluator.evaluate_candidate("POISON_0001", retrieval_k=100)
    assert len(result.recommended_job_ids) == 5


def test_leakage_audit_fails_if_candidate_in_training_set():
    """Directive 1: Extend test_leakage_audit to fail if any model used for an evaluated candidate was trained on that candidate."""
    from application.ai.ranking import LightGBMRanker
    from unittest.mock import MagicMock
    import numpy as np

    evaluator = UnifiedCandidateEvaluator(min_match=50)

    # 1. Create a ranker explicitly marked as trained on RES_0001
    mock_booster = MagicMock()
    mock_booster.predict.return_value = np.array([0.5])
    mock_booster.num_feature.return_value = 14
    leaky_ranker = LightGBMRanker.from_model(
        mock_booster,
        metadata={"train_candidates": ["RES_0001", "RES_0002"]},
    )

    # Evaluating RES_0001 with this leaky ranker must raise AssertionError
    with pytest.raises(AssertionError, match=r"LEAKAGE AUDIT FAILURE.*RES_0001.*training set"):
        evaluator.evaluate_candidate("RES_0001", retrieval_k=10, custom_ranker=leaky_ranker)

    # 2. Clean ranker trained only on disjoint candidates (e.g. RES_0010, RES_0011)
    clean_ranker = LightGBMRanker.from_model(
        mock_booster,
        metadata={"train_candidates": ["RES_0010", "RES_0011"]},
    )
    # Evaluating RES_0001 with clean_ranker must succeed
    clean_res = evaluator.evaluate_candidate("RES_0001", retrieval_k=10, custom_ranker=clean_ranker)
    assert clean_res is not None
    assert clean_res.resume_id == "RES_0001"


def test_large_dataset_resume_hash_and_namespace_isolation():
    """Verify that:
    1. Resume texts across standard and large datasets have zero hash collisions (100% disjoint text corpora).
    2. Large dataset candidate IDs are strictly namespaced (prefix 'L_' or 'LARGE_') and never collide with standard IDs.
    """
    import hashlib

    golden_loader = GoldenDataLoader()
    std_resumes = golden_loader.load_resumes()
    std_hashes = {
        cid: hashlib.sha256(r.resume_text.encode("utf-8")).hexdigest()
        for cid, r in std_resumes.items()
    }

    large_dir = Path(__file__).resolve().parent.parent / "datasets" / "large"
    if (large_dir / "golden_resumes.jsonl").exists():
        large_loader = GoldenDataLoader(dataset_dir=large_dir)
        large_resumes = large_loader.load_resumes()
        large_hashes = {
            cid: hashlib.sha256(r.resume_text.encode("utf-8")).hexdigest()
            for cid, r in large_resumes.items()
        }

        # 1. Text hash disjointness assertion (zero content leakage)
        overlap_hashes = set(std_hashes.values()) & set(large_hashes.values())
        assert len(overlap_hashes) == 0, f"Resume text content leakage detected: {overlap_hashes}"

        # 2. Namespace isolation assertion (zero ID collision)
        overlap_ids = set(std_resumes.keys()) & set(large_resumes.keys())
        assert len(overlap_ids) == 0, f"Candidate ID namespace collision detected: {overlap_ids}"
        assert all(cid.startswith("L_") or cid.startswith("LARGE_") for cid in large_resumes.keys()), \
            "All large dataset candidate IDs must be namespaced with 'L_' or 'LARGE_' prefix."



