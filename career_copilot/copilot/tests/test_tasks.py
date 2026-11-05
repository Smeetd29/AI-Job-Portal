from unittest.mock import patch
from datetime import datetime, timezone, timedelta
import pytest
from copilot.models import QueueItem
from copilot.tasks import (
    run_daily_for_all_candidates,
    run_candidate_pipeline,
    apply_item_task,
    expire_stale_queue_items,
)
from .factories import CandidateProfileFactory, JobPreferenceFactory, QueueItemFactory, JobFactory


@pytest.fixture
def candidates_batch(db):
    # Candidate 1: Enabled
    p1 = CandidateProfileFactory(full_name="Active Cand 1")
    JobPreferenceFactory(candidate=p1, agent_enabled=True)

    # Candidate 2: Enabled
    p2 = CandidateProfileFactory(full_name="Active Cand 2")
    JobPreferenceFactory(candidate=p2, agent_enabled=True)

    # Candidate 3: Disabled
    p3 = CandidateProfileFactory(full_name="Paused Cand 3")
    JobPreferenceFactory(candidate=p3, agent_enabled=False)

    return p1, p2, p3


def test_fan_out_daily_run(candidates_batch):
    p1, p2, p3 = candidates_batch

    with patch("copilot.tasks.run_candidate_pipeline.delay") as mock_delay:
        count = run_daily_for_all_candidates()

    assert count == 2
    assert mock_delay.call_count == 2
    called_ids = {call.args[0] for call in mock_delay.call_args_list}
    assert str(p1.id) in called_ids
    assert str(p2.id) in called_ids
    assert str(p3.id) not in called_ids


@patch("copilot.services.pipeline.run_for_candidate")
def test_run_candidate_pipeline_task(mock_run, db):
    profile = CandidateProfileFactory()
    JobPreferenceFactory(candidate=profile, agent_enabled=True)

    mock_run.return_value = None
    result = run_candidate_pipeline(str(profile.id))
    mock_run.assert_called_once_with(str(profile.id))
    assert result == "Candidate skipped or paused"


def test_apply_item_task(db):
    job = JobFactory(apply_url="https://example.com/apply/123")
    item = QueueItemFactory(job=job, status="PENDING")

    res = apply_item_task(str(item.id))
    assert res.get("method") == "link"
    assert res.get("apply_url") == "https://example.com/apply/123"

    item.refresh_from_db()
    assert item.status == "APPLIED"


def test_expire_stale_queue_items_task(db):
    now = datetime.now(timezone.utc)
    # Stale item
    stale = QueueItemFactory(
        status="PENDING",
        expires_at=now - timedelta(days=1),
    )
    # Active item
    active = QueueItemFactory(
        status="PENDING",
        expires_at=now + timedelta(days=2),
    )

    expired_count = expire_stale_queue_items()
    assert expired_count == 1

    stale.refresh_from_db()
    active.refresh_from_db()
    assert stale.status == "EXPIRED"
    assert active.status == "PENDING"
