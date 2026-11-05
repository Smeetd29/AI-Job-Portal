from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from users.models import User, CandidateProfile, RecruiterProfile
from jobs.models import Job
from application.models import Application
from agents.models import AgentAction, AgentRun, ScreeningAgentSettings
from agents.tools import classify_score, write_rationale
from agents.graph import execute_screening_agent

class ScreeningAgentTestCase(TestCase):
    def setUp(self):
        self.recruiter = User.objects.create_user(username="recruiter1", email="rec@corp.com", password="pass")
        self.recruiter_profile = RecruiterProfile.objects.create(
            user=self.recruiter, company_name="Tech Solutions"
        )
        self.candidate = User.objects.create_user(username="cand1", email="cand@mail.com", password="pass")
        self.profile = CandidateProfile.objects.create(
            user=self.candidate,
            skills="Python, Django, React, PostgreSQL",
            bio="Backend developer with 4 years experience",
        )
        self.job = Job.objects.create(
            recruiter=self.recruiter,
            title="Senior Python Backend Developer",
            pay_amount=130000,
            category="Engineering",
            description="Looking for Python, Django and PostgreSQL experience",
        )
        self.settings = ScreeningAgentSettings.objects.create(
            recruiter=self.recruiter,
            enabled=True,
            shortlist_threshold=80,
            reject_threshold=40,
            auto_execute_extreme_scores=False,
        )
        self.client = APIClient()

    def test_deterministic_score_classification(self):
        self.assertEqual(classify_score(85, self.settings), "shortlist")
        self.assertEqual(classify_score(35, self.settings), "reject")
        self.assertEqual(classify_score(65, self.settings), "review")

    def test_write_rationale(self):
        rationale = write_rationale(
            candidate_name="cand1",
            job_title=self.job.title,
            score=88,
            decision="shortlist",
            matching_points=[{"point": "Strong Python knowledge", "evidence": "4 years experience"}],
            gaps=[],
        )
        self.assertIsInstance(rationale, str)
        self.assertGreater(len(rationale), 10)

    def test_screening_execution_queued_for_approval(self):
        app = Application.objects.create(
            job=self.job,
            candidate=self.candidate,
            full_name="Candidate One",
            email="cand@mail.com",
            graduation_year=2024,
            status="PENDING",
        )

        result = execute_screening_agent(application_id=app.id)
        self.assertNotIn("error", result)

        action = AgentAction.objects.filter(
            agent_type="screening",
            object_id=app.id,
        ).first()
        self.assertIsNotNone(action)
        self.assertEqual(action.status, "pending")
        self.assertTrue(action.requires_approval)

    def test_screening_auto_execute_extreme_scores(self):
        self.settings.auto_execute_extreme_scores = True
        self.settings.save()

        app = Application.objects.create(
            job=self.job,
            candidate=self.candidate,
            full_name="Candidate High Match",
            email="cand@mail.com",
            graduation_year=2024,
            status="PENDING",
        )

        result = execute_screening_agent(application_id=app.id)
        action = AgentAction.objects.filter(agent_type="screening", object_id=app.id).first()
        self.assertIsNotNone(action)

    def test_screening_approve_and_override_api(self):
        self.client.force_authenticate(user=self.recruiter)
        app = Application.objects.create(
            job=self.job,
            candidate=self.candidate,
            full_name="Candidate Review",
            email="cand@mail.com",
            graduation_year=2024,
            status="PENDING",
        )
        action = AgentAction.objects.filter(job=self.job, user=self.candidate, agent_type="screening").first()
        if not action:
            run = AgentRun.objects.create(agent_type="screening", user=self.candidate)
            action = AgentAction.objects.create(
                run=run,
                job=self.job,
                user=self.candidate,
                agent_type="screening",
                object_id=app.id,
                action_type="screening_shortlist",
                payload={"decision": "shortlist", "score": 85, "rationale": "High skills overlap"},
                status="pending",
                requires_approval=True,
            )
        else:
            action.payload = {"decision": "shortlist", "score": 85, "rationale": "High skills overlap"}
            action.status = "pending"
            action.requires_approval = True
            action.save()

        url_queue = reverse("screening-queue")
        res_queue = self.client.get(url_queue)
        self.assertEqual(res_queue.status_code, status.HTTP_200_OK)
        self.assertEqual(len(res_queue.data), 1)

        url_approve = reverse("screening-approve", kwargs={"action_id": action.id})
        res_approve = self.client.post(url_approve)
        self.assertEqual(res_approve.status_code, status.HTTP_200_OK)

        action.refresh_from_db()
        app.refresh_from_db()
        self.assertEqual(action.status, "approved")
        self.assertEqual(app.status, "SHORTLISTED")
