from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from users.models import User, CandidateProfile, RecruiterProfile
from jobs.models import Job
from application.models import Application
from agents.models import AgentAction, DigestSubscription
from agents.tools import get_new_jobs_since, template_reason
from agents.graph import execute_digest_agent

class DigestAgentTestCase(TestCase):
    def setUp(self):
        self.recruiter = User.objects.create_user(username="rec_digest", email="rec@mail.com", password="pass")
        self.recruiter_profile = RecruiterProfile.objects.create(
            user=self.recruiter, company_name="Alpha Tech"
        )
        self.candidate = User.objects.create_user(username="cand_digest", email="cand@mail.com", password="pass")
        self.profile = CandidateProfile.objects.create(
            user=self.candidate,
            skills="Python, Django, FastAPI",
            bio="Python developer",
        )
        self.subscription = DigestSubscription.objects.create(
            user=self.candidate,
            frequency="weekly",
            min_score_threshold=40,
            max_jobs_per_digest=3,
        )
        self.job1 = Job.objects.create(
            recruiter=self.recruiter,
            title="Python Software Engineer",
            pay_amount=110000,
            category="Engineering",
            description="Django and FastAPI experience required",
        )

        self.recruiter2 = User.objects.create_user(username="rec_digest2", email="rec2@mail.com", password="pass")
        self.recruiter_profile2 = RecruiterProfile.objects.create(
            user=self.recruiter2, company_name="Beta Analytics"
        )
        self.job2 = Job.objects.create(
            recruiter=self.recruiter2,
            title="Data Analyst",
            pay_amount=85000,
            category="Data",
            description="Excel and SQL required",
        )
        self.client = APIClient()

    def test_get_new_jobs_since_excludes_applied(self):
        Application.objects.create(
            job=self.job1,
            candidate=self.candidate,
            full_name="Candidate",
            email="cand@mail.com",
            graduation_year=2024,
        )

        unapplied = get_new_jobs_since(self.candidate, since_date=None)
        unapplied_ids = [j.id for j in unapplied]
        self.assertNotIn(self.job1.id, unapplied_ids)
        self.assertIn(self.job2.id, unapplied_ids)

    def test_template_reason(self):
        reason = template_reason(
            self.job1,
            {
                "key_skills": ["Python", "Django"],
                "matching_points": [{"point": "3+ years Python experience"}],
            },
        )
        self.assertIn("Python", reason)

    def test_execute_digest_agent(self):
        result = execute_digest_agent(user_id=self.candidate.id, trigger="scheduled")
        self.assertNotIn("error", result)

        self.subscription.refresh_from_db()
        self.assertIsNotNone(self.subscription.last_sent_at)

        actions = AgentAction.objects.filter(user=self.candidate, agent_type="digest")
        self.assertTrue(actions.exists())

    def test_digest_api_settings_and_send_now(self):
        self.client.force_authenticate(user=self.candidate)

        url_settings = reverse("digest-settings")
        res_get = self.client.get(url_settings)
        self.assertEqual(res_get.status_code, status.HTTP_200_OK)
        self.assertEqual(res_get.data["frequency"], "weekly")

        res_put = self.client.put(url_settings, {"frequency": "daily", "min_score_threshold": 60})
        self.assertEqual(res_put.status_code, status.HTTP_200_OK)
        self.assertEqual(res_put.data["frequency"], "daily")

        url_send = reverse("digest-send-now")
        res_send = self.client.post(url_send)
        self.assertEqual(res_send.status_code, status.HTTP_200_OK)
