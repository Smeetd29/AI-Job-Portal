import pytest
from rest_framework.test import APIClient
from .factories import (
    UserFactory,
    CandidateProfileFactory,
    JobPreferenceFactory,
    JobFactory,
    QueueItemFactory,
)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return UserFactory()


@pytest.fixture
def profile(user):
    return CandidateProfileFactory(user=user)


@pytest.fixture
def preference(profile):
    return JobPreferenceFactory(candidate=profile)


@pytest.fixture
def job():
    return JobFactory()


@pytest.fixture
def queue_item(profile, job):
    return QueueItemFactory(candidate=profile, job=job)
