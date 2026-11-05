from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from users.models import User, CandidateProfile, RecruiterProfile
from jobs.models import Job
from application.models import Application
from agents.models import AgentAction, AutoApplySettings
from agents.tools import get_eligible_jobs, draft_cover_letter
from agents.graph import execute_auto_apply_agent

class AutoApplyAgentTestCase(TestCase):
    def setUp(self):
        self.recruiter = User.objects.create_user(username="rec_apply", email="rec@mail.com", password="pass")
        self.recruiter_profile = RecruiterProfile.objects.create(
            user=self.recruiter, company_name="CloudCo"
        )
        self.candidate = User.objects.create_user(username="cand_apply", email="cand@mail.com", password="pass")
        self.profile = CandidateProfile.objects.create(
            user=self.candidate,
            skills="Python, Django, AWS",
            bio="Full stack cloud engineer",
        )
        self.settings = AutoApplySettings.objects.create(
            user=self.candidate,
            enabled=True,
            min_score_threshold=40,
            mode="review_first",
            daily_cap=3,
            excluded_companies=["BannedCorp"],
        )
        self.job1 = Job.objects.create(
            recruiter=self.recruiter,
            title="Backend Cloud Engineer",
            pay_amount=125000,
            category="Engineering",
            description="Python and AWS role",
        )

        self.recruiter_banned = User.objects.create_user(username="rec_banned", email="banned@corp.com", password="pass")
        self.recruiter_banned_profile = RecruiterProfile.objects.create(
            user=self.recruiter_banned, company_name="BannedCorp"
        )
        self.job_excluded = Job.objects.create(
            recruiter=self.recruiter_banned,
            title="DevOps Engineer",
            pay_amount=115000,
            category="Engineering",
            description="Python and AWS",
        )
        self.client = APIClient()

    def test_get_eligible_jobs_excludes_banned_company(self):
        eligible = get_eligible_jobs(self.candidate, self.settings)
        eligible_companies = [j.company_name for j in eligible]
        self.assertIn("CloudCo", eligible_companies)
        self.assertNotIn("BannedCorp", eligible_companies)

    def test_draft_cover_letter_under_200_words(self):
        letter = draft_cover_letter(
            self.candidate,
            self.job1,
            {"key_skills": ["Python", "AWS"], "matching_points": [{"point": "AWS Certified"}]},
        )
        word_count = len(letter.split())
        self.assertLess(word_count, 200)

    def test_review_first_mode_creates_draft_and_pending_action(self):
        result = execute_auto_apply_agent(self.candidate.id, trigger="scheduled")
        self.assertNotIn("error", result)

        action = AgentAction.objects.filter(
            user=self.candidate,
            job=self.job1,
            agent_type="auto_apply",
        ).first()
        self.assertIsNotNone(action)
        self.assertEqual(action.status, "pending")
        self.assertTrue(action.requires_approval)

        app = Application.objects.filter(candidate=self.candidate, job=self.job1).first()
        self.assertIsNotNone(app)
        self.assertEqual(app.status, "DRAFT")
        self.assertEqual(app.source, "auto_apply")

    def test_auto_submit_mode_submits_directly(self):
        self.settings.mode = "auto_submit"
        self.settings.save()

        result = execute_auto_apply_agent(self.candidate.id, trigger="scheduled")
        self.assertNotIn("error", result)

        action = AgentAction.objects.filter(
            user=self.candidate,
            job=self.job1,
            agent_type="auto_apply",
        ).first()
        self.assertIsNotNone(action)
        self.assertEqual(action.status, "auto_executed")
        self.assertTrue(action.executed)

        app = Application.objects.filter(candidate=self.candidate, job=self.job1).first()
        self.assertEqual(app.status, "PENDING")

    def test_candidate_review_queue_approve_and_edit_api(self):
        self.client.force_authenticate(user=self.candidate)

        execute_auto_apply_agent(self.candidate.id, trigger="manual")
        action = AgentAction.objects.filter(user=self.candidate, agent_type="auto_apply", status="pending").first()
        self.assertIsNotNone(action)

        res_pending = self.client.get(reverse("auto-apply-pending"))
        self.assertEqual(res_pending.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(res_pending.data), 1)

        url_edit = reverse("auto-apply-edit-and-approve", kwargs={"action_id": action.id})
        res_edit = self.client.post(url_edit, {"cover_letter": "Custom tailored letter from candidate."})
        self.assertEqual(res_edit.status_code, status.HTTP_200_OK)

        action.refresh_from_db()
        app = Application.objects.get(id=action.object_id)
        self.assertEqual(action.status, "approved")
        self.assertEqual(app.status, "PENDING")
        self.assertEqual(app.cover_letter, "Custom tailored letter from candidate.")
