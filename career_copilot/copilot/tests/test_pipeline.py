from unittest.mock import patch, MagicMock
import pytest
from django.utils import timezone
from copilot.services.pipeline import run_for_candidate
from copilot.sources.base import JobSource, JobDTO
from copilot.models import QueueItem, AgentRun
from .factories import CandidateProfileFactory, JobPreferenceFactory


@pytest.fixture
def candidate_setup(db):
    profile = CandidateProfileFactory(
        full_name="Alice Smith",
        skills=["Python", "Django", "PostgreSQL", "Celery", "Redis"],
    )
    pref = JobPreferenceFactory(
        candidate=profile,
        target_titles=["Backend Engineer", "Python Developer"],
        min_salary=1800000,
        salary_currency="INR",
        work_modes=["remote", "hybrid"],
        locations=["Mumbai"],
        exclude_companies=["BadCompany Inc"],
        max_queue_per_day=5,
        min_match_score=0.50,
        agent_enabled=True,
    )
    return profile, pref


@patch("copilot.services.pipeline.generate_cover_note")
def test_pipeline_happy_path(mock_cover_note, candidate_setup, settings):
    profile, pref = candidate_setup
    settings.ENABLED_JOB_SOURCES = ["mock"]
    mock_cover_note.return_value = ("Tailored note for Alice", "claude-sonnet-5-5")

    run = run_for_candidate(profile.id)

    assert run is not None
    assert run.status == "OK"
    assert run.jobs_fetched == 5
    assert run.items_queued > 0

    items = QueueItem.objects.filter(candidate=profile)
    assert items.count() == run.items_queued
    for item in items:
        assert item.status == "PENDING"
        assert item.cover_note == "Tailored note for Alice"
        assert item.cover_note_model == "claude-sonnet-5-5"
        assert item.expires_at > timezone.now()


@patch("copilot.services.pipeline.generate_cover_note")
def test_pipeline_idempotency_second_run(mock_cover_note, candidate_setup, settings):
    profile, pref = candidate_setup
    settings.ENABLED_JOB_SOURCES = ["mock"]
    mock_cover_note.return_value = ("Tailored note", "claude-sonnet-5-5")

    # Run 1
    run1 = run_for_candidate(profile.id)
    initial_count = QueueItem.objects.filter(candidate=profile).count()
    assert initial_count > 0

    # Run 2 immediately
    run2 = run_for_candidate(profile.id)
    assert run2 is not None
    assert run2.items_queued == 0
    assert QueueItem.objects.filter(candidate=profile).count() == initial_count


@patch("copilot.services.pipeline.generate_cover_note")
def test_pipeline_daily_cap(mock_cover_note, candidate_setup, settings):
    profile, pref = candidate_setup
    settings.ENABLED_JOB_SOURCES = ["mock"]
    pref.max_queue_per_day = 2
    pref.save()

    mock_cover_note.return_value = ("Tailored note", "claude-sonnet-5-5")

    run = run_for_candidate(profile.id)
    assert run.items_queued <= 2
    assert QueueItem.objects.filter(candidate=profile).count() <= 2


class BrokenJobSource(JobSource):
    name = "broken"

    def fetch(self, *, titles, since=None):
        raise RuntimeError("External API network failure")


@patch("copilot.services.pipeline.generate_cover_note")
def test_pipeline_failing_source_gives_partial(mock_cover_note, candidate_setup, settings):
    profile, pref = candidate_setup
    settings.ENABLED_JOB_SOURCES = ["mock"]
    mock_cover_note.return_value = ("Tailored note", "claude-sonnet-5-5")

    from copilot.sources.mock import MockJobSource
    mock_sources = [MockJobSource(), BrokenJobSource()]

    with patch("copilot.services.pipeline.get_enabled_sources", return_value=mock_sources):
        run = run_for_candidate(profile.id)

    assert run.status == "PARTIAL"
    assert "broken: External API network failure" in run.error
    assert run.items_queued > 0


def test_pipeline_agent_disabled_noop(candidate_setup, settings):
    profile, pref = candidate_setup
    pref.agent_enabled = False
    pref.save()

    run = run_for_candidate(profile.id)
    assert run is None
    assert QueueItem.objects.filter(candidate=profile).count() == 0
    assert AgentRun.objects.filter(candidate=profile).count() == 0


@patch("copilot.services.pipeline.generate_cover_note")
def test_pipeline_re_queues_archived_jobs(mock_cover_note, candidate_setup, settings):
    profile, pref = candidate_setup
    settings.ENABLED_JOB_SOURCES = ["mock"]
    mock_cover_note.return_value = ("Tailored note", "claude-sonnet-5-5")

    run1 = run_for_candidate(profile.id)
    assert run1.items_queued > 0
    items = QueueItem.objects.filter(candidate=profile)
    assert items.count() > 0

    # Soft archive all queue items
    QueueItem.objects.filter(candidate=profile).update(archived_at=timezone.now(), archive_batch="batch_test")

    # Run again: because previous items are archived, dedupe ignores them and re-queues
    run2 = run_for_candidate(profile.id)
    assert run2.items_queued > 0
    total_items = QueueItem.objects.filter(candidate=profile)
    assert total_items.filter(archived_at__isnull=False).count() == run1.items_queued
    assert total_items.filter(archived_at__isnull=True).count() == run2.items_queued

