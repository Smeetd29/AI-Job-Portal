import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Union
from uuid import UUID
from django.conf import settings
from django.db import transaction
from django.utils import timezone as dj_timezone

from ..models import CandidateProfile, JobPreference, Job, QueueItem, AgentRun
from ..sources import get_enabled_sources
from .matching import evaluate
from .cover_note import generate_cover_note, CoverNoteError

logger = logging.getLogger(__name__)


def run_for_candidate(candidate_id: Union[UUID, str]) -> Optional[AgentRun]:
    """
    Orchestrates one candidate's daily autonomous career co-pilot run:
    1. Loads profile and preference; aborts if agent is paused (agent_enabled=False).
    2. Records an AgentRun audit log.
    3. Fetches new jobs from all enabled sources with fault tolerance (PARTIAL status on source error).
    4. Upserts jobs into the Job database.
    5. Filters out jobs already queued for this candidate.
    6. Evaluates and scores jobs against candidate preferences.
    7. Respects the 24h daily quota limit.
    8. Generates tailored cover notes with Claude and queues items as PENDING with TTL.
    9. Finalizes timestamps and audit counters.
    """
    try:
        profile = CandidateProfile.objects.select_related("preference").get(id=candidate_id)
    except CandidateProfile.DoesNotExist:
        logger.error(f"CandidateProfile {candidate_id} not found.")
        return None

    try:
        pref = profile.preference
    except JobPreference.DoesNotExist:
        logger.warning(f"CandidateProfile {candidate_id} has no JobPreference configured.")
        return None

    # Step 1: If agent_enabled is False, do nothing
    if not pref.agent_enabled:
        logger.info(f"Agent is disabled for candidate {candidate_id}. Skipping run.")
        return None

    # Step 2: Create AgentRun
    run = AgentRun.objects.create(
        candidate=profile,
        status="OK",
    )

    now = dj_timezone.now()
    since = pref.last_run_at or (now - timedelta(days=7))

    # Step 3: Fetch jobs from all enabled sources
    sources = get_enabled_sources()
    fetched_dtos = []
    source_errors = []

    for source in sources:
        try:
            dtos = source.fetch(titles=pref.target_titles or [], since=since)
            fetched_dtos.extend(dtos)
        except Exception as exc:
            logger.exception(f"Job source '{source.name}' encountered error: {exc}")
            source_errors.append(f"{source.name}: {str(exc)}")

    if source_errors:
        if sources and len(source_errors) == len(sources):
            run.status = "ERROR"
        else:
            run.status = "PARTIAL"
        run.error = "; ".join(source_errors)

    # Step 4: Upsert jobs into Job model
    upserted_jobs = []
    for dto in fetched_dtos:
        job_obj, _ = Job.objects.update_or_create(
            source=dto.source,
            external_id=dto.external_id,
            defaults={
                "title": dto.title,
                "company": dto.company,
                "location": dto.location,
                "work_mode": dto.work_mode,
                "salary_min": dto.salary_min,
                "salary_max": dto.salary_max,
                "salary_currency": dto.salary_currency,
                "description": dto.description,
                "apply_url": dto.apply_url,
                "posted_at": dto.posted_at,
                "raw": dto.raw or {},
            },
        )
        upserted_jobs.append(job_obj)

    run.jobs_fetched = len(upserted_jobs)

    # Step 5: Skip jobs already present in QueueItem for this candidate (ignoring archived items)
    existing_job_ids = set(
        QueueItem.objects.filter(candidate=profile, archived_at__isnull=True).values_list("job_id", flat=True)
    )
    unreviewed_jobs = [j for j in upserted_jobs if j.id not in existing_job_ids]

    # Step 6: Evaluate remaining jobs
    passing_job_evals = []
    for job in unreviewed_jobs:
        match_res = evaluate(job, pref, profile)
        if match_res.passed:
            passing_job_evals.append((job, match_res))

    # Sort descending by match score
    passing_job_evals.sort(key=lambda pair: pair[1].score, reverse=True)
    run.jobs_matched = len(passing_job_evals)

    # Step 7: Enforce daily quota
    max_queue_per_day = pref.max_queue_per_day or getattr(settings, "DEFAULT_MAX_QUEUE_PER_DAY", 10)
    items_created_24h = QueueItem.objects.filter(
        candidate=profile,
        created_at__gte=now - timedelta(hours=24),
    ).count()

    remaining_quota = max(0, max_queue_per_day - items_created_24h)
    jobs_to_queue = passing_job_evals[:remaining_quota]

    # Step 8: Generate cover notes and queue items
    ttl_days = getattr(settings, "QUEUE_ITEM_TTL_DAYS", 7)
    items_queued_count = 0
    default_model = getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-5-5")

    for job, match_res in jobs_to_queue:
        note_text = ""
        model_used = default_model
        try:
            note_text, model_used = generate_cover_note(job, profile)
        except CoverNoteError as cne:
            logger.warning(f"Cover note generation failed for job {job.id}: {cne}. Queuing with empty note.")
            note_text = ""
        except Exception as exc:
            logger.error(f"Unexpected error creating cover note: {exc}. Queuing with empty note.")
            note_text = ""

        with transaction.atomic():
            QueueItem.objects.create(
                candidate=profile,
                job=job,
                match_score=match_res.score,
                match_reasons=match_res.reasons,
                cover_note=note_text,
                cover_note_model=model_used,
                status="PENDING",
                expires_at=now + timedelta(days=ttl_days),
            )
            items_queued_count += 1

    # Step 9: Finalize
    pref.last_run_at = now
    pref.save(update_fields=["last_run_at"])

    run.items_queued = items_queued_count
    run.finished_at = dj_timezone.now()
    run.save()

    return run
