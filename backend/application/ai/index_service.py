from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import List, Optional, Tuple
from django.conf import settings
from application.ai.matching import FaissRetriever, SentenceTransformerEmbedding

logger = logging.getLogger(__name__)

class FAISSIndexManager:
    _lock = threading.Lock()
    _instance: Optional[FaissRetriever] = None
    _last_loaded_mtime: float = 0.0

    @classmethod
    def get_index_dir(cls) -> Path:
        target = getattr(settings, "FAISS_INDEX_DIR", None)
        if target:
            p = Path(target)
        else:
            p = Path(settings.BASE_DIR) / "data" / "faiss_index"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def get_index(cls) -> FaissRetriever:
        """Returns worker singleton instance of FaissRetriever, loading from disk if needed."""
        with cls._lock:
            index_dir = cls.get_index_dir()
            index_file = index_dir / "index.faiss"

            # Check if file was modified on disk by a rebuild task
            current_mtime = index_file.stat().st_mtime if index_file.exists() else 0.0

            if cls._instance is not None and current_mtime == cls._last_loaded_mtime:
                return cls._instance

            retriever = FaissRetriever(embedding_dim=384)
            if index_file.exists():
                try:
                    retriever.load(str(index_dir))
                    cls._instance = retriever
                    cls._last_loaded_mtime = current_mtime
                    logger.info("Loaded persisted FAISS index from %s (%d documents)", index_dir, retriever.total_documents)
                    return cls._instance
                except Exception as exc:
                    logger.warning("Could not load FAISS index from %s: %s. Building empty index.", index_dir, exc)

            cls._instance = retriever
            cls._last_loaded_mtime = 0.0
            return cls._instance

    @classmethod
    def rebuild_job_index(cls) -> int:
        """Rebuilds the FAISS index from all active jobs and persists to disk."""
        from jobs.models import Job

        index_dir = cls.get_index_dir()
        logger.info("Rebuilding FAISS job index at %s", index_dir)

        active_jobs = list(Job.objects.filter(is_active=True).values("id", "title", "description", "category"))
        if not active_jobs:
            logger.info("No active jobs found for FAISS index.")
            retriever = FaissRetriever(embedding_dim=384)
            retriever.save(str(index_dir))
            with cls._lock:
                cls._instance = retriever
            return 0

        job_ids = [j["id"] for j in active_jobs]
        texts = [f"{j['title']}. {j.get('category', '')}. {j['description'][:600]}" for j in active_jobs]

        embedder = SentenceTransformerEmbedding(lazy_load=False)
        vectors = embedder.embed_batch(texts)

        new_retriever = FaissRetriever(embedding_dim=embedder.embedding_dim)
        new_retriever.add_documents(job_ids, vectors)
        new_retriever.save(str(index_dir))

        with cls._lock:
            cls._instance = new_retriever
            index_file = index_dir / "index.faiss"
            cls._last_loaded_mtime = index_file.stat().st_mtime if index_file.exists() else 0.0

        logger.info("FAISS index rebuilt successfully with %d jobs", len(job_ids))
        return len(job_ids)
