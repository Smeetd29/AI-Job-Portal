import logging
from celery import shared_task
from .models import CandidateProfile, QueueItem
from .services import pipeline, applier, approval

logger = logging.getLogger(__name__)


@shared_task
def run_daily_for_all_candidates() -> int:
    """
    Daily Celery Beat task that fans out individual candidate pipeline runs
    for all candidates with active job preferences (agent_enabled=True).
    """
    active_candidate_ids = (
        CandidateProfile.objects.filter(preference__agent_enabled=True)
        .values_list("id", flat=True)
        .iterator()
    )

    dispatched = 0
    for cand_id in active_candidate_ids:
        run_candidate_pipeline.delay(str(cand_id))
        dispatched += 1

    logger.info(f"Dispatched daily career co-pilot pipeline for {dispatched} candidates.")
    return dispatched


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, max_retries=3)
def run_candidate_pipeline(self, candidate_id: str) -> str:
    """
    Executes the autonomous search, matching, and cover note pipeline for a single candidate.
    """
    logger.info(f"Starting pipeline for candidate {candidate_id}")
    run = pipeline.run_for_candidate(candidate_id)
    if run:
        return f"Run {run.id} finished with status {run.status} ({run.items_queued} queued)"
    return "Candidate skipped or paused"


@shared_task
def apply_item_task(item_id: str) -> dict:
    """
    Celery task that executes the application action once approved by candidate.
    """
    try:
        item = QueueItem.objects.select_related("job", "candidate").get(id=item_id)
    except QueueItem.DoesNotExist:
        logger.error(f"QueueItem {item_id} not found for apply task.")
        return {"error": "QueueItem not found"}

    return applier.apply(item)


@shared_task
def expire_stale_queue_items() -> int:
    """
    Scheduled task to mark expired unreviewed queue items as EXPIRED.
    """
    count = approval.expire_stale()
    logger.info(f"Expired {count} stale queue items.")
    return count
