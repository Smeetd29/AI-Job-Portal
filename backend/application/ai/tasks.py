from __future__ import annotations

import logging
from celery import shared_task
from django.core.cache import cache

logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    name="application.ai.tasks.rebuild_faiss_index_task",
    max_retries=2,
    default_retry_delay=60,
)
def rebuild_faiss_index_task(self):
    """Celery task to rebuild and persist the FAISS index on a schedule or event."""
    lock_key = "lock:task:rebuild_faiss_index"
    acquired = cache.add(lock_key, "building", timeout=600)
    if not acquired:
        logger.info("FAISS index rebuild task is already running; skipping.")
        return {"status": "skipped_already_running"}

    try:
        from application.ai.index_service import FAISSIndexManager
        count = FAISSIndexManager.rebuild_job_index()
        return {"status": "completed", "indexed_jobs": count}
    except Exception as exc:
        logger.exception("Failed to rebuild FAISS index: %s", exc)
        raise self.retry(exc=exc)
    finally:
        cache.delete(lock_key)
