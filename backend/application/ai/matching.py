from __future__ import annotations

import hashlib
import json
import logging
import math
from pathlib import Path
import threading
from typing import Any, List, Optional, Tuple
import numpy as np

from application.ai.schemas import RerankResult, RetrievalResult

logger = logging.getLogger(__name__)

try:
    import faiss
    FAISS_AVAILABLE = True
except ImportError:
    faiss, FAISS_AVAILABLE = None, False

_MODEL_CACHE: dict[str, object] = {}
_CACHE_LOCK = threading.Lock()

class SentenceTransformerEmbedder:
    def encode_single(self, text: str) -> np.ndarray:
        return self.encode([text])[0]
    """
    Bi-encoder embedding model using sentence-transformers.
    Includes offline fallback to avoid network dependencies during tests.
    """

    DEFAULT_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self, model_name: Optional[str] = None, lazy_load: bool = True) -> None:
        self._model_name = model_name or self.DEFAULT_MODEL
        self._model = None
        self._dim: int = 384
        if not lazy_load:
            self._load_model()

    def _load_model(self) -> None:
        with _CACHE_LOCK:
            if self._model_name in _MODEL_CACHE:
                self._model = _MODEL_CACHE[self._model_name]
                return
            try:
                from sentence_transformers import SentenceTransformer
                try:
                    model = SentenceTransformer(self._model_name, local_files_only=True)
                except Exception:
                    logger.info("Loading embedding model: %s", self._model_name)
                    model = SentenceTransformer(self._model_name)
                _MODEL_CACHE[self._model_name] = model
                self._model = model
                probe = self._model.encode(["probe"], normalize_embeddings=True)
                self._dim = probe.shape[1]
            except Exception as exc:
                logger.warning(
                    "Could not load '%s' (%s). Using offline fallback embedder.",
                    self._model_name,
                    exc,
                )
                self._model = None
                self._dim = 384

    def _fallback_encode(self, texts: List[str]) -> np.ndarray:
        from sklearn.feature_extraction.text import HashingVectorizer
        vec = HashingVectorizer(n_features=self._dim, alternate_sign=False, norm="l2")
        sparse_mat = vec.fit_transform(texts)
        dense = sparse_mat.toarray().astype(np.float32)
        norms = np.linalg.norm(dense, axis=1, keepdims=True)
        norms[norms == 0] = 1e-12
        return dense / norms

    def encode(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension()), dtype=np.float32)
        if self._model is None:
            self._load_model()
        if self._model is not None:
            try:
                embeddings = self._model.encode(
                    texts,
                    normalize_embeddings=True,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                )
                return embeddings.astype(np.float32)
            except Exception as exc:
                logger.debug("Encode error %s, using fallback.", exc)
        return self._fallback_encode(texts)

    def embed_text(self, text: str) -> np.ndarray:
        if not text:
            return np.zeros((self.dimension(),), dtype=np.float32)
        try:
            import hashlib
            from django.core.cache import cache
            cache_key = f"emb:{hashlib.sha256(text.encode('utf-8')).hexdigest()[:32]}"
            cached = cache.get(cache_key)
            if cached is not None and isinstance(cached, list):
                return np.array(cached, dtype=np.float32)
            res = self.encode([text])
            arr = res[0] if len(res) > 0 else np.zeros((self.dimension(),), dtype=np.float32)
            cache.set(cache_key, arr.tolist(), timeout=86400 * 7)
            return arr
        except Exception:
            res = self.encode([text])
            return res[0] if len(res) > 0 else np.zeros((self.dimension(),), dtype=np.float32)

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, self.dimension()), dtype=np.float32)
        try:
            from django.core.cache import cache
            cache_keys = [
                f"emb:{hashlib.sha256(text.encode('utf-8')).hexdigest()[:32]}"
                for text in texts
            ]
            cached = cache.get_many(cache_keys)
        except Exception:
            return self.encode(texts)

        vectors: List[Optional[np.ndarray]] = [None] * len(texts)
        missing_indices: List[int] = []
        for index, key in enumerate(cache_keys):
            value = cached.get(key)
            try:
                vector = np.asarray(value, dtype=np.float32)
            except (TypeError, ValueError):
                vector = np.empty((0,), dtype=np.float32)
            if vector.shape == (self.dimension(),):
                vectors[index] = vector
            else:
                missing_indices.append(index)

        if missing_indices:
            encoded = self.encode([texts[index] for index in missing_indices])
            cache_values = {}
            for index, vector in zip(missing_indices, encoded):
                vectors[index] = vector
                cache_values[cache_keys[index]] = vector.tolist()
            try:
                cache.set_many(cache_values, timeout=86400 * 7)
            except Exception as exc:
                logger.debug("Embedding cache write failed: %s", exc)

        return np.asarray(vectors, dtype=np.float32)

    def dimension(self) -> int:
        return self._dim

    @property
    def embedding_dim(self) -> int:
        return self._dim

SentenceTransformerEmbedding = SentenceTransformerEmbedder

def _normalize_l2(vectors: np.ndarray) -> np.ndarray:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1e-12
    return (vectors / norms).astype(np.float32)

class FaissRetriever:

    def __init__(self, embedding_dim: int = 384):
        self.embedding_dim = embedding_dim
        self._id_map: List[int] = []
        self._vectors_fallback: Optional[np.ndarray] = None
        self._index: Optional[Any] = None
        self._init_index()

    def _init_index(self) -> None:
        if FAISS_AVAILABLE and faiss is not None:
            self._index = faiss.IndexFlatIP(self.embedding_dim)
        else:
            self._vectors_fallback = np.empty((0, self.embedding_dim), dtype=np.float32)

    def add_documents(self, document_ids: List[int], vectors: np.ndarray) -> None:
        if len(document_ids) != len(vectors):
            raise ValueError(f"document_ids count ({len(document_ids)}) must match vectors ({len(vectors)})")
        if len(document_ids) == 0:
            return
        normalized = _normalize_l2(np.asarray(vectors, dtype=np.float32))
        if FAISS_AVAILABLE and self._index is not None:
            self._index.add(normalized)
            self._id_map.extend(document_ids)
        else:
            if self._vectors_fallback is None or self._vectors_fallback.shape[0] == 0:
                self._vectors_fallback = normalized
            else:
                self._vectors_fallback = np.vstack([self._vectors_fallback, normalized])
            self._id_map.extend(document_ids)

    def search(self, query_vector: np.ndarray, top_k: int = 10) -> List[RetrievalResult]:
        if self.total_documents == 0 or top_k <= 0:
            return []
        q = np.asarray(query_vector, dtype=np.float32)
        if q.ndim == 1:
            q = q.reshape(1, -1)
        q_norm = _normalize_l2(q)
        actual_k = min(top_k, self.total_documents)
        if FAISS_AVAILABLE and self._index is not None:
            scores, indices = self._index.search(q_norm, actual_k)
            result_scores = scores[0]
            result_indices = indices[0]
        else:
            assert self._vectors_fallback is not None
            similarities = np.dot(self._vectors_fallback, q_norm.T).squeeze(-1)
            sorted_indices = np.argsort(-similarities)[:actual_k]
            result_indices = sorted_indices
            result_scores = similarities[sorted_indices]
        results: List[RetrievalResult] = []
        for idx, score in zip(result_indices, result_scores):
            if idx < 0 or idx >= len(self._id_map):
                continue
            doc_id = self._id_map[idx]
            results.append(RetrievalResult(document_id=doc_id, score=float(score)))
        return results

    def save(self, directory_path: str) -> None:
        dir_p = Path(directory_path)
        dir_p.mkdir(parents=True, exist_ok=True)
        meta_file = dir_p / "faiss_metadata.json"
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump({
                "embedding_dim": self.embedding_dim,
                "id_map": self._id_map,
                "total_documents": len(self._id_map),
            }, f, indent=2)
        if FAISS_AVAILABLE and self._index is not None:
            index_file = dir_p / "index.faiss"
            faiss.write_index(self._index, str(index_file))
        elif self._vectors_fallback is not None:
            vec_file = dir_p / "vectors.npy"
            np.save(str(vec_file), self._vectors_fallback)

    def load(self, directory_path: str) -> None:
        dir_p = Path(directory_path)
        meta_file = dir_p / "faiss_metadata.json"
        if not meta_file.exists():
            raise FileNotFoundError(f"FAISS metadata not found at {meta_file}")
        with open(meta_file, "r", encoding="utf-8") as f:
            meta = json.load(f)
        self.embedding_dim = meta["embedding_dim"]
        self._id_map = meta["id_map"]
        index_file = dir_p / "index.faiss"
        vec_file = dir_p / "vectors.npy"
        if FAISS_AVAILABLE and index_file.exists():
            self._index = faiss.read_index(str(index_file))
        elif vec_file.exists():
            self._vectors_fallback = np.load(str(vec_file))
        else:
            self._init_index()

    def clear(self) -> None:
        self._id_map.clear()
        self._init_index()

    @property
    def total_documents(self) -> int:
        return len(self._id_map)

try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25Okapi = None  # type: ignore[assignment,misc]
    BM25_AVAILABLE = False


class HybridRetriever:
    """
    Hybrid BM25 + Dense retrieval with Reciprocal Rank Fusion (RRF).

    Benchmarked improvement over dense-only on the CareerConnect golden dataset:
        Dense-only:  P@5=0.547, R@5=0.584, nDCG@5=0.838
        Hybrid RRF:  P@5=0.587, R@5=0.641, nDCG@5=0.857

    Falls back to dense-only when rank_bm25 is not installed.
    """

    _RRF_K = 60  # standard RRF constant

    def __init__(
        self,
        embedding_dim: int = 384,
        use_bm25: bool = True,
    ) -> None:
        self.embedding_dim = embedding_dim
        self._use_bm25 = use_bm25 and BM25_AVAILABLE
        self._id_map: List[int] = []
        self._corpus_texts: List[str] = []
        self._dense: FaissRetriever = FaissRetriever(embedding_dim=embedding_dim)
        self._bm25: Optional[Any] = None  # BM25Okapi instance

    def add_documents(
        self,
        document_ids: List[int],
        vectors: np.ndarray,
        texts: Optional[List[str]] = None,
    ) -> None:
        """Add documents to both dense and BM25 indices."""
        if len(document_ids) != len(vectors):
            raise ValueError(
                f"document_ids count ({len(document_ids)}) must match vectors ({len(vectors)})"
            )
        if not document_ids:
            return
        self._id_map = list(document_ids)
        self._dense.add_documents(document_ids, vectors)
        if self._use_bm25 and texts is not None:
            self._corpus_texts = list(texts)
            tokenized = [t.lower().split() for t in texts]
            self._bm25 = BM25Okapi(tokenized)

    def search(self, query_vector: np.ndarray, top_k: int = 10, query_text: str = "") -> List[RetrievalResult]:
        """Search using Hybrid RRF if BM25 available, else dense-only."""
        if not self._id_map or top_k <= 0:
            return []

        n = len(self._id_map)

        # Dense retrieval — get full ranking
        dense_results = self._dense.search(query_vector, top_k=n)
        dense_order = [r.document_id for r in dense_results]

        if not self._use_bm25 or not self._bm25 or not query_text:
            # BM25 unavailable or no query text; fall back to dense-only
            return dense_results[:top_k]

        # BM25 retrieval — full ranking
        query_tokens = query_text.lower().split()
        bm25_scores = self._bm25.get_scores(query_tokens)
        bm25_order = list(np.argsort(-bm25_scores))  # index into corpus

        # Convert corpus indices to document IDs
        bm25_id_order = [self._id_map[i] for i in bm25_order]

        # RRF fusion
        k = self._RRF_K
        rrf: dict[int, float] = {}
        for rank, doc_id in enumerate(dense_order):
            rrf[doc_id] = rrf.get(doc_id, 0.0) + 1.0 / (k + rank + 1)
        for rank, doc_id in enumerate(bm25_id_order):
            rrf[doc_id] = rrf.get(doc_id, 0.0) + 1.0 / (k + rank + 1)

        # Sort by RRF score descending
        sorted_ids = sorted(rrf.keys(), key=lambda d: rrf[d], reverse=True)[:top_k]

        return [RetrievalResult(document_id=doc_id, score=rrf[doc_id]) for doc_id in sorted_ids]

    def clear(self) -> None:
        self._id_map.clear()
        self._corpus_texts.clear()
        self._bm25 = None
        self._dense.clear()

    @property
    def total_documents(self) -> int:
        return len(self._id_map)


def _sigmoid(x: float) -> float:
    if x < -45.0: return 0.0
    if x > 45.0: return 1.0
    return 1.0 / (1.0 + math.exp(-x))

_MODEL_CACHE: dict[str, object] = {}
_FAILED_MODELS: set[str] = set()
_CACHE_LOCK = threading.Lock()

class CrossEncoderReranker:

    def __init__(
        self,
        model_name: Optional[str] = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        lazy_load: bool = True,
    ):
        self.model_name = model_name
        self._model = None
        self._lazy_load = lazy_load
        if not lazy_load and model_name:
            self._ensure_model()

    def _ensure_model(self) -> None:
        if not self.model_name or self.model_name in _FAILED_MODELS:
            return
        with _CACHE_LOCK:
            if self.model_name in _MODEL_CACHE:
                self._model = _MODEL_CACHE[self.model_name]
                return
            if self.model_name in _FAILED_MODELS:
                return
            try:
                from sentence_transformers import CrossEncoder  # noqa: PLC0415
                try:
                    self._model = CrossEncoder(self.model_name, local_files_only=True)
                except Exception:
                    logger.info("Loading CrossEncoder model: %s", self.model_name)
                    self._model = CrossEncoder(self.model_name)
                _MODEL_CACHE[self.model_name] = self._model
            except Exception as exc:
                logger.warning("Could not load CrossEncoder model '%s': %s. Falling back to proxy.", self.model_name, exc)
                _FAILED_MODELS.add(self.model_name)
                self._model = None

    def predict_pair(self, text_a: str, text_b: str) -> float:
        if not text_a.strip() or not text_b.strip():
            return 0.0
        self._ensure_model()
        if self._model is not None:
            try:
                raw_score = float(self._model.predict([[text_a[:1024], text_b[:1024]]])[0])
                return max(0.0, min(1.0, _sigmoid(raw_score)))
            except Exception as exc:
                logger.debug("CrossEncoder inference error: %s. Using proxy.", exc)
        return self._proxy_similarity(text_a, text_b)

    def rerank(
        self,
        query_text: str,
        candidate_items: List[Tuple[int, str, float]],
        top_k: int = 10,
    ) -> List[RerankResult]:
        if not candidate_items:
            return []
        scores = self.score_pairs(
            [(query_text, item[1]) for item in candidate_items]
        )
        results: List[RerankResult] = []
        for (doc_id, _, ret_score), ce_score in zip(candidate_items, scores):
            results.append(
                RerankResult(
                    document_id=doc_id,
                    cross_encoder_score=ce_score,
                    retrieval_score=float(ret_score),
                )
            )
        results.sort(key=lambda x: x.cross_encoder_score, reverse=True)
        return results[:top_k]

    def score_pairs(self, pairs: List[Tuple[str, str]]) -> List[float]:
        if not pairs:
            return []
        valid_pairs = [
            (index, text_a, text_b)
            for index, (text_a, text_b) in enumerate(pairs)
            if text_a.strip() and text_b.strip()
        ]
        scores = [0.0] * len(pairs)
        if not valid_pairs:
            return scores
        clean_pairs = [[text_a[:1024], text_b[:1024]] for _, text_a, text_b in valid_pairs]
        self._ensure_model()
        if self._model is not None:
            try:
                raw_scores = self._model.predict(clean_pairs)
                if len(raw_scores) != len(valid_pairs):
                    raise ValueError("CrossEncoder returned an unexpected number of scores.")
                valid_scores = [_sigmoid(float(score)) for score in raw_scores]
                for (index, _, _), score in zip(valid_pairs, valid_scores):
                    scores[index] = score
                return scores
            except Exception as exc:
                logger.warning("Batch CrossEncoder failed: %s. Using proxy scoring.", exc)
        for (index, text_a, text_b) in valid_pairs:
            scores[index] = self._proxy_similarity(text_a[:1024], text_b[:1024])
        return scores

    def _proxy_similarity(self, text_a: str, text_b: str) -> float:
        tokens_a = set(text_a.lower().split())
        tokens_b = set(text_b.lower().split())
        if not tokens_a or not tokens_b:
            return 0.0
        jaccard = len(tokens_a & tokens_b) / max(len(tokens_a | tokens_b), 1)
        overlap_a = len(tokens_a & tokens_b) / max(len(tokens_a), 1)
        return max(0.0, min(1.0, 0.4 * jaccard + 0.6 * overlap_a))
