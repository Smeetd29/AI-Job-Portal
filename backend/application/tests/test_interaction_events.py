from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import User, CandidateProfile, RecruiterProfile
from jobs.models import Job
from application.models import InteractionEvent


class InteractionEventAPITests(APITestCase):
    def setUp(self):
        # Candidate 1
        self.candidate1 = User.objects.create_user(
            username="candidate1",
            email="candidate1@example.com",
            password="password123",
            is_candidate=True,
        )
        CandidateProfile.objects.create(user=self.candidate1)

        # Candidate 2
        self.candidate2 = User.objects.create_user(
            username="candidate2",
            email="candidate2@example.com",
            password="password123",
            is_candidate=True,
        )
        CandidateProfile.objects.create(user=self.candidate2)

        # Recruiter 1
        self.recruiter1 = User.objects.create_user(
            username="recruiter1",
            email="recruiter1@example.com",
            password="password123",
            is_recruiter=True,
        )
        RecruiterProfile.objects.create(user=self.recruiter1, company_name="Tech Alpha")

        # Recruiter 2
        self.recruiter2 = User.objects.create_user(
            username="recruiter2",
            email="recruiter2@example.com",
            password="password123",
            is_recruiter=True,
        )
        RecruiterProfile.objects.create(user=self.recruiter2, company_name="Tech Beta")

        # Job 1 owned by recruiter1
        self.job1 = Job.objects.create(
            recruiter=self.recruiter1,
            title="Senior Python Engineer",
            description="Build scalable microservices with Django and FastAPI.",
            pay_amount=Decimal("120000.00"),
            category="Engineering",
            location_type="Remote",
            job_type="Full Time",
            is_active=True,
        )
        # Job 2 owned by recruiter2
        self.job2 = Job.objects.create(
            recruiter=self.recruiter2,
            title="Frontend Developer",
            description="Build React and TypeScript dashboards.",
            pay_amount=Decimal("95000.00"),
            category="Engineering",
            location_type="Remote",
            job_type="Full Time",
            is_active=True,
        )
        self.url = reverse("interaction-events")

    def test_unauthenticated_request_rejected(self):
        payload = {
            "candidate": self.candidate1.id,
            "job": self.job1.id,
            "event_type": "job_view",
        }
        res = self.client.post(self.url, payload, format="json")
        self.assertIn(res.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_candidate_can_record_job_view_and_save(self):
        self.client.force_authenticate(user=self.candidate1)
        payload = {
            "candidate": self.candidate1.id,
            "job": self.job1.id,
            "event_type": "job_view",
            "session_id": "sess_123",
            "recommendation_position": 1,
            "model_version": "v3.0.0",
            "event_source": "web_recommendations",
        }
        res = self.client.post(self.url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["event_type"], "job_view")
        self.assertEqual(res.data["candidate"], self.candidate1.id)
        self.assertEqual(res.data["job"], self.job1.id)
        self.assertEqual(InteractionEvent.objects.count(), 1)

    def test_candidate_cannot_record_event_for_another_candidate(self):
        self.client.force_authenticate(user=self.candidate1)
        payload = {
            "candidate": self.candidate2.id,  # Trying to record event for candidate2
            "job": self.job1.id,
            "event_type": "job_view",
        }
        res = self.client.post(self.url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(InteractionEvent.objects.count(), 0)

    def test_rapid_duplicate_events_are_deduplicated(self):
        self.client.force_authenticate(user=self.candidate1)
        payload = {
            "candidate": self.candidate1.id,
            "job": self.job1.id,
            "event_type": "job_view",
            "session_id": "sess_rapid",
        }
        # First view
        res1 = self.client.post(self.url, payload, format="json")
        self.assertEqual(res1.status_code, status.HTTP_201_CREATED)
        # Second identical view in rapid succession
        res2 = self.client.post(self.url, payload, format="json")
        self.assertEqual(res2.status_code, status.HTTP_201_CREATED)
        # Should reuse event / not duplicate database row
        self.assertEqual(InteractionEvent.objects.count(), 1)

    def test_recruiter_can_record_shortlist_for_own_job(self):
        self.client.force_authenticate(user=self.recruiter1)
        payload = {
            "candidate": self.candidate1.id,
            "job": self.job1.id,
            "event_type": "recruiter_shortlist",
        }
        res = self.client.post(self.url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["event_type"], "recruiter_shortlist")

    def test_recruiter_cannot_record_outcome_for_other_recruiter_job(self):
        self.client.force_authenticate(user=self.recruiter1)
        payload = {
            "candidate": self.candidate1.id,
            "job": self.job2.id,  # Owned by recruiter2!
            "event_type": "recruiter_shortlist",
        }
        res = self.client.post(self.url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(InteractionEvent.objects.count(), 0)

    def test_candidate_cannot_record_recruiter_outcome(self):
        self.client.force_authenticate(user=self.candidate1)
        payload = {
            "candidate": self.candidate1.id,
            "job": self.job1.id,
            "event_type": "offer",  # Recruiter event
        }
        res = self.client.post(self.url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_batch_event_submission(self):
        self.client.force_authenticate(user=self.candidate1)
        payload = [
            {
                "candidate": self.candidate1.id,
                "job": self.job1.id,
                "event_type": "job_view",
                "session_id": "sess_batch",
                "recommendation_position": 1,
            },
            {
                "candidate": self.candidate1.id,
                "job": self.job2.id,
                "event_type": "job_view",
                "session_id": "sess_batch",
                "recommendation_position": 2,
            },
        ]
        res = self.client.post(self.url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertEqual(res.data["created"], 2)
        self.assertEqual(InteractionEvent.objects.count(), 2)

    def test_get_interaction_events_filtered_by_candidate(self):
        self.client.force_authenticate(user=self.candidate1)
        InteractionEvent.objects.create(
            candidate=self.candidate1,
            job=self.job1,
            event_type="job_view",
        )
        InteractionEvent.objects.create(
            candidate=self.candidate2,
            job=self.job2,
            event_type="job_view",
        )
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        # Candidate 1 should only see their own event
        self.assertEqual(len(res.data), 1)
        self.assertEqual(res.data[0]["candidate"], self.candidate1.id)
