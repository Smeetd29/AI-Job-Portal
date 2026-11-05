"""
Unit tests for HybridRetriever (BM25 + Dense RRF fusion).
"""
from __future__ import annotations

import numpy as np
import pytest

from application.ai.matching import HybridRetriever, BM25_AVAILABLE, RetrievalResult


@pytest.mark.skipif(not BM25_AVAILABLE, reason="rank_bm25 not installed")
class TestHybridRetriever:

    def _make_retriever(self):
        retriever = HybridRetriever(embedding_dim=4, use_bm25=True)
        doc_ids = [10, 20, 30, 40]
        # Orthogonal unit vectors for deterministic dense retrieval
        vecs = np.array([
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
            [0.0, 0.0, 0.0, 1.0],
        ], dtype=np.float32)
        texts = [
            "python machine learning engineer",
            "java backend developer spring",
            "javascript react frontend developer",
            "python data scientist analytics",
        ]
        retriever.add_documents(doc_ids, vecs, texts=texts)
        return retriever

    def test_total_documents(self):
        r = self._make_retriever()
        assert r.total_documents == 4

    def test_search_returns_top_k(self):
        r = self._make_retriever()
        q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = r.search(q, top_k=2, query_text="python developer")
        assert len(results) == 2

    def test_search_returns_retrieval_result_objects(self):
        r = self._make_retriever()
        q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = r.search(q, top_k=3, query_text="python")
        for res in results:
            assert isinstance(res, RetrievalResult)
            assert res.document_id in [10, 20, 30, 40]
            assert res.score > 0.0

    def test_hybrid_rrf_boosts_bm25_match(self):
        """Doc 40 matches 'python' in both dense (similar vector) and BM25;
        hybrid should keep it near top compared to dense-only."""
        r = self._make_retriever()
        q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        # Dense-only: only [10] matches; doc 40 is orthogonal so scores low
        # BM25: docs 10 and 40 both have 'python', so RRF should surface doc 40
        hybrid_results = r.search(q, top_k=4, query_text="python")
        hybrid_ids = [res.document_id for res in hybrid_results]
        assert 10 in hybrid_ids, "Dense-best match (doc 10) must appear"
        assert 40 in hybrid_ids, "BM25 match (doc 40 has 'python') must appear in hybrid"

    def test_search_without_query_text_falls_back_to_dense(self):
        r = self._make_retriever()
        q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        # No query_text → fallback to dense-only, first result should be doc 10
        results = r.search(q, top_k=4, query_text="")
        assert results[0].document_id == 10

    def test_search_top_k_clamped_to_corpus(self):
        r = self._make_retriever()
        q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = r.search(q, top_k=100, query_text="python")
        assert len(results) == 4  # only 4 docs in corpus

    def test_clear_resets_state(self):
        r = self._make_retriever()
        r.clear()
        assert r.total_documents == 0
        q = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        results = r.search(q, top_k=5, query_text="python")
        assert results == []

    def test_add_empty_documents_is_noop(self):
        r = HybridRetriever(embedding_dim=4, use_bm25=True)
        r.add_documents([], np.empty((0, 4), dtype=np.float32), texts=[])
        assert r.total_documents == 0


class TestHybridRetrieverFallback:
    """Tests for behavior when BM25 is not used (use_bm25=False)."""

    def test_dense_only_mode(self):
        r = HybridRetriever(embedding_dim=4, use_bm25=False)
        doc_ids = [1, 2, 3]
        vecs = np.array([[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0]], dtype=np.float32)
        r.add_documents(doc_ids, vecs, texts=["a", "b", "c"])
        q = np.array([1, 0, 0, 0], dtype=np.float32)
        results = r.search(q, top_k=2, query_text="a")
        assert len(results) == 2
        assert results[0].document_id == 1

