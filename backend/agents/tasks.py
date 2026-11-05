from __future__ import annotations

import logging
from datetime import timedelta
from celery import shared_task
from django.utils import timezone

from django.core.cache import cache

logger = logging.getLogger(__name__)

@shared_task(
    bind=True,
    name="agents.tasks.run_screening_agent",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
)
def run_screening_agent(self, application_id: int):
    lock_key = f"lock:task:run_screening_agent:{application_id}"
    acquired = cache.add(lock_key, "running", timeout=300)
    if not acquired:
        logger.warning("Duplicate screening task for Application %s detected; skipping for idempotency", application_id)
        return {"status": "skipped_duplicate", "application_id": application_id}
    try:
        from agents.graph import execute_screening_agent
        logger.info("Starting screening agent task for Application ID %s", application_id)
        return execute_screening_agent(application_id=application_id, trigger="event")
    finally:
        cache.delete(lock_key)

@shared_task(
    bind=True,
    name="agents.tasks.run_digest_dispatch",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
)
def run_digest_dispatch(self):
    lock_key = "lock:task:run_digest_dispatch"
    acquired = cache.add(lock_key, "running", timeout=900)
    if not acquired:
        logger.info("Digest dispatch scan already running; skipping.")
        return {"status": "skipped_already_running"}
    try:
        from agents.models import DigestSubscription
        from agents.graph import execute_digest_agent

        logger.info("Starting periodic digest dispatch scan.")
        subscriptions = DigestSubscription.objects.exclude(frequency="off")
        results = []

        for sub in subscriptions:
            try:
                res = execute_digest_agent(user_id=sub.user_id, trigger="scheduled")
                results.append({"user_id": sub.user_id, "result": res})
            except Exception as e:
                logger.exception("Failed to run digest for user %s: %s", sub.user_id, e)
                results.append({"user_id": sub.user_id, "error": str(e)})

        return {"processed": len(results), "details": results}
    finally:
        cache.delete(lock_key)

@shared_task(
    bind=True,
    name="agents.tasks.run_auto_apply_scan",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
)
def run_auto_apply_scan(self):
    lock_key = "lock:task:run_auto_apply_scan"
    acquired = cache.add(lock_key, "running", timeout=900)
    if not acquired:
        logger.info("Auto-apply scan already running; skipping.")
        return {"status": "skipped_already_running"}
    try:
        from agents.models import AutoApplySettings
        from agents.graph import execute_auto_apply_agent

        logger.info("Starting periodic auto-apply scan.")
        active_settings = AutoApplySettings.objects.filter(enabled=True)
        results = []

        for s in active_settings:
            try:
                res = execute_auto_apply_agent(user_id=s.user_id, trigger="scheduled")
                results.append({"user_id": s.user_id, "result": res})
            except Exception as e:
                logger.exception("Failed to run auto-apply for user %s: %s", s.user_id, e)
                results.append({"user_id": s.user_id, "error": str(e)})

        return {"processed": len(results), "details": results}
    finally:
        cache.delete(lock_key)

@shared_task(
    bind=True,
    name="agents.tasks.run_scheduling_agent",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_jitter=True,
    max_retries=3,
)
def run_scheduling_agent(self, application_id: int):
    lock_key = f"lock:task:run_scheduling_agent:{application_id}"
    acquired = cache.add(lock_key, "running", timeout=300)
    if not acquired:
        logger.warning("Duplicate scheduling task for Application %s detected; skipping", application_id)
        return {"status": "skipped_duplicate", "application_id": application_id}
    try:
        from agents.graph import execute_scheduling_agent
        logger.info("Starting scheduling agent task for Application ID %s", application_id)
        return execute_scheduling_agent(application_id=application_id, trigger="event")
    finally:
        cache.delete(lock_key)

@shared_task(name="agents.tasks.sweep_expired_proposals")
def sweep_expired_proposals():
    from agents.models import InterviewSlotProposal, AgentAction
    from django.contrib.contenttypes.models import ContentType

    cutoff = timezone.now() - timedelta(hours=72)
    expired_qs = InterviewSlotProposal.objects.filter(status="pending", created_at__lt=cutoff)
    count = expired_qs.count()

    if count > 0:
        proposal_ct = ContentType.objects.get_for_model(InterviewSlotProposal)
        expired_ids = list(expired_qs.values_list("id", flat=True))

        expired_qs.update(status="expired")
        AgentAction.objects.filter(
            content_type=proposal_ct,
            object_id__in=expired_ids,
            status="pending",
        ).update(status="expired")

        logger.info("Expired %s pending interview slot proposals", count)

    return {"expired_count": count}
