from django.test import TestCase, override_settings

from users.models import User, RecruiterProfile
from jobs.models import Job
from agents.models import AgentRun, AgentAction
from agents.guardrails import (
    is_screening_enabled,
    is_digest_enabled,
    is_auto_apply_enabled,
    is_scheduling_enabled,
    is_agent_enabled,
    check_weekly_cap_reached,
    check_weekly_ceiling,
)

class GuardrailsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test_candidate", email="cand@test.com", password="pass")
        self.recruiter = User.objects.create_user(username="test_recruiter", email="rec@test.com", password="pass")
        self.recruiter_profile = RecruiterProfile.objects.create(
            user=self.recruiter, company_name="Acme Corp"
        )
        self.job = Job.objects.create(
            recruiter=self.recruiter,
            title="Software Engineer",
            pay_amount=120000,
            category="Engineering",
            description="Python engineer with Django experience",
        )
        self.run = AgentRun.objects.create(agent_type="auto_apply", user=self.user)

    def test_kill_switches_default(self):
        self.assertTrue(is_screening_enabled())
        self.assertTrue(is_digest_enabled())
        self.assertTrue(is_auto_apply_enabled())
        self.assertTrue(is_scheduling_enabled())
        self.assertTrue(is_agent_enabled("screening"))
        self.assertTrue(is_agent_enabled("auto_apply"))

    @override_settings(SCREENING_AGENT_ENABLED=False)
    def test_screening_kill_switch_override(self):
        self.assertFalse(is_screening_enabled())
        self.assertFalse(is_agent_enabled("screening"))

    @override_settings(AUTO_APPLY_AGENT_ENABLED=False)
    def test_auto_apply_kill_switch_override(self):
        self.assertFalse(is_auto_apply_enabled())
        self.assertFalse(is_agent_enabled("auto_apply"))

    def test_weekly_cap_under_limit(self):
        self.assertFalse(check_weekly_cap_reached(self.user.id))
        self.assertTrue(check_weekly_ceiling(self.user))

    def test_weekly_cap_reached_at_25(self):
        for i in range(25):
            dummy_job = Job.objects.create(
                recruiter=self.recruiter,
                title=f"Job {i}",
                pay_amount=90000,
                category="Engineering",
                description="test role",
            )
            AgentAction.objects.create(
                run=self.run,
                user=self.user,
                job=dummy_job,
                agent_type="auto_apply",
                action_type="auto_apply_auto_submit",
                status="auto_executed",
                executed=True,
            )

        self.assertTrue(check_weekly_cap_reached(self.user.id))
        self.assertFalse(check_weekly_ceiling(self.user))
