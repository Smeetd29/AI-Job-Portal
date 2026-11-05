import pytest
from rest_framework import status
from .factories import (
    UserFactory,
    CandidateProfileFactory,
    JobPreferenceFactory,
    JobFactory,
    QueueItemFactory,
)


@pytest.fixture
def auth_user_and_item(db, api_client):
    user = UserFactory(username="applicant1")
    profile = CandidateProfileFactory(user=user)
    pref = JobPreferenceFactory(candidate=profile)
    job = JobFactory(apply_url="https://jobs.example.com/apply/backend-101")
    item = QueueItemFactory(
        candidate=profile,
        job=job,
        status="PENDING",
        cover_note="Original cover note drafted by Claude.",
    )
    api_client.force_authenticate(user=user)
    return user, profile, pref, job, item


def test_approve_happy_path(auth_user_and_item, api_client):
    user, profile, pref, job, item = auth_user_and_item
    url = f"/api/queue/{item.id}/approve/"

    resp = api_client.post(url, format="json")
    assert resp.status_code == status.HTTP_200_OK

    data = resp.json()
    assert data["status"] == "APPLIED"
    assert data["apply_url"] == job.apply_url
    assert data["cover_note"] == "Original cover note drafted by Claude."

    item.refresh_from_db()
    assert item.status == "APPLIED"
    assert item.apply_result.get("method") == "link"


def test_double_approve_returns_409(auth_user_and_item, api_client):
    user, profile, pref, job, item = auth_user_and_item
    url = f"/api/queue/{item.id}/approve/"

    # First approve succeeds
    resp1 = api_client.post(url, format="json")
    assert resp1.status_code == status.HTTP_200_OK

    # Second approve returns 409 Conflict
    resp2 = api_client.post(url, format="json")
    assert resp2.status_code == status.HTTP_409_CONFLICT
    assert "Item" in resp2.json().get("error", "")


def test_other_user_item_returns_404(auth_user_and_item, api_client):
    user, profile, pref, job, item = auth_user_and_item

    # Authenticate as a different user
    other_user = UserFactory(username="other_applicant")
    CandidateProfileFactory(user=other_user)
    api_client.force_authenticate(user=other_user)

    # Attempt to access or approve user 1's item
    detail_url = f"/api/queue/{item.id}/"
    approve_url = f"/api/queue/{item.id}/approve/"

    detail_resp = api_client.get(detail_url)
    assert detail_resp.status_code == status.HTTP_404_NOT_FOUND

    approve_resp = api_client.post(approve_url, format="json")
    assert approve_resp.status_code == status.HTTP_404_NOT_FOUND


def test_approve_persists_edited_note(auth_user_and_item, api_client):
    user, profile, pref, job, item = auth_user_and_item
    url = f"/api/queue/{item.id}/approve/"

    edited = "This is my personalized, hand-edited cover note with specific achievements."
    resp = api_client.post(url, {"cover_note": edited}, format="json")
    assert resp.status_code == status.HTTP_200_OK

    item.refresh_from_db()
    assert item.cover_note == edited
    assert item.status == "APPLIED"


def test_reject_item(auth_user_and_item, api_client):
    user, profile, pref, job, item = auth_user_and_item
    url = f"/api/queue/{item.id}/reject/"

    resp = api_client.post(url, format="json")
    assert resp.status_code == status.HTTP_200_OK

    item.refresh_from_db()
    assert item.status == "REJECTED"

    # Rejecting again returns 409
    resp_again = api_client.post(url, format="json")
    assert resp_again.status_code == status.HTTP_409_CONFLICT


def test_approve_all(auth_user_and_item, api_client):
    user, profile, pref, job, item1 = auth_user_and_item
    item2 = QueueItemFactory(
        candidate=profile,
        job=JobFactory(),
        status="PENDING",
    )

    url = "/api/queue/approve-all/"
    payload = {"ids": [str(item1.id), str(item2.id)]}

    resp = api_client.post(url, payload, format="json")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["approved_count"] == 2
    assert str(item1.id) in data["approved_ids"]
    assert str(item2.id) in data["approved_ids"]

    item1.refresh_from_db()
    item2.refresh_from_db()
    assert item1.status == "APPLIED"
    assert item2.status == "APPLIED"


def test_preferences_api(auth_user_and_item, api_client):
    user, profile, pref, job, item = auth_user_and_item
    url = "/api/preferences/"

    # GET
    get_resp = api_client.get(url)
    assert get_resp.status_code == status.HTTP_200_OK
    assert get_resp.json()["min_salary"] == pref.min_salary

    # PUT
    put_resp = api_client.put(
        url,
        {
            "min_salary": 2400000,
            "target_titles": ["Staff Backend Engineer"],
        },
        format="json",
    )
    assert put_resp.status_code == status.HTTP_200_OK
    pref.refresh_from_db()
    assert pref.min_salary == 2400000
    assert pref.target_titles == ["Staff Backend Engineer"]


def test_agent_pause_and_resume(auth_user_and_item, api_client):
    user, profile, pref, job, item = auth_user_and_item

    # Pause
    pause_resp = api_client.post("/api/agent/pause/")
    assert pause_resp.status_code == status.HTTP_200_OK
    pref.refresh_from_db()
    assert not pref.agent_enabled

    # Resume
    resume_resp = api_client.post("/api/agent/resume/")
    assert resume_resp.status_code == status.HTTP_200_OK
    pref.refresh_from_db()
    assert pref.agent_enabled


def test_queue_list_filter(auth_user_and_item, api_client):
    user, profile, pref, job, item = auth_user_and_item
    # Add an expired item
    QueueItemFactory(candidate=profile, status="EXPIRED")

    # Filter PENDING
    resp_pending = api_client.get("/api/queue/?status=PENDING")
    assert resp_pending.status_code == status.HTTP_200_OK
    data = resp_pending.json()
    assert len(data) == 1
    assert data[0]["id"] == str(item.id)

    # Filter EXPIRED
    resp_expired = api_client.get("/api/queue/?status=EXPIRED")
    assert resp_expired.status_code == status.HTTP_200_OK
    assert len(resp_expired.json()) == 1


def test_custom_applier_backend(auth_user_and_item, settings):
    from copilot.services.applier import apply, get_applier
    user, profile, pref, job, item = auth_user_and_item

    # Custom backend
    settings.APPLIER_BACKEND = "copilot.services.applier.LinkApplier"
    applier_instance = get_applier()
    assert applier_instance.__class__.__name__ == "LinkApplier"

    # Invalid backend falls back to LinkApplier
    settings.APPLIER_BACKEND = "invalid.module.UnknownApplier"
    fallback_instance = get_applier()
    assert fallback_instance.__class__.__name__ == "LinkApplier"


def test_applier_failure_sets_failed_status(auth_user_and_item):
    from unittest.mock import patch
    from copilot.services.applier import apply
    user, profile, pref, job, item = auth_user_and_item

    with patch("copilot.services.applier.LinkApplier.apply", side_effect=ValueError("ATS down")):
        with pytest.raises(ValueError):
            apply(item)

    item.refresh_from_db()
    assert item.status == "FAILED"
    assert "ATS down" in item.apply_result.get("error", "")
