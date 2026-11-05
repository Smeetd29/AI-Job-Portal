from __future__ import annotations

import logging
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from application.models import Application
from jobs.models import Job
from users.models import CandidateProfile
from application.ai.recommendations import invalidate_recommendation_cache

logger = logging.getLogger(__name__)

@receiver(post_save, sender=CandidateProfile)
def on_candidate_profile_updated(sender, instance, **kwargs):
    logger.debug("CandidateProfile updated for user %s, invalidating recommendations cache", instance.user_id)
    invalidate_recommendation_cache(candidate_user_id=instance.user_id)

@receiver([post_save, post_delete], sender=Job)
def on_job_changed(sender, instance, **kwargs):
    logger.debug("Job %s changed, invalidating global recommendation cache and scheduling FAISS update", instance.id)
    invalidate_recommendation_cache(candidate_user_id=None)
    try:
        from application.ai.tasks import rebuild_faiss_index_task
        rebuild_faiss_index_task.delay()
    except Exception:
        pass

@receiver(post_save, sender=Application)
def on_application_created(sender, instance, created, **kwargs):
    if created:
        logger.debug("Application created for candidate %s on job %s, invalidating cache", instance.candidate_id, instance.job_id)
        invalidate_recommendation_cache(candidate_user_id=instance.candidate_id)
