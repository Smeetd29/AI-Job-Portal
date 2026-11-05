from __future__ import annotations

from unittest.mock import patch
from django.test import TestCase
from django.core import mail
from django.db import IntegrityError
from django.utils import timezone
from datetime import timedelta
import redis.exceptions

from users.models import User, RecruiterProfile, CandidateProfile
from jobs.models import Job
from application.models import Application
from agents.models import AgentRun, AgentAction, AutoApplySettings
from agents.guardrails import (
    HARD_WEEKLY_APPLICATION_CEILING,
    check_weekly_cap_reached,
    check_weekly_ceiling,
    get_weekly_application_count,
)
from agents.tools import (
    count_applications_today,
    create_or_submit_application,
    notify_candidate_batch,
)
from agents.graph import auto_apply_graph, check_eligibility_caps_node


class CapResilienceTestCase(TestCase):
    """
    Validates PostgreSQL as the authoritative source of truth for:
    1. Weekly hard application ceiling (25).
    2. Daily quota enforcement.
    3. Resilience when Redis drops/dies mid-run.
    4. Prevention of double-apply (DB unique constraint).
    5. Prevention of double-email (notification idempotency).
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username="resilient_candidate",
            email="candidate@test.com",
            password="securepassword123",
        )
        self.candidate_profile = CandidateProfile.objects.create(
            user=self.user,
            phone="+1234567890",
            skills="Python, Django, PostgreSQL, Docker",
        )
        self.settings = AutoApplySettings.objects.create(
            user=self.user,
            enabled=True,
            daily_cap=3,
            min_score_threshold=80,
            mode="auto_submit",
        )
        self.recruiter = User.objects.create_user(
            username="resilient_recruiter",
            email="recruiter@test.com",
            password="securepassword123",
        )
        self.recruiter_profile = RecruiterProfile.objects.create(
            user=self.recruiter,
            company_name="Resilience Corp",
        )
        self.run = AgentRun.objects.create(
            agent_type="auto_apply",
            user=self.user,
        )
        self.jobs = [
            Job.objects.create(
                recruiter=self.recruiter,
                title=f"Engineer {i}",
                pay_amount=120000,
                category="Engineering",
                description="Python and PostgreSQL engineer needed.",
            )
            for i in range(30)
        ]

    def test_weekly_cap_enforced_in_postgres_when_redis_dies(self):
        """Simulate Redis dying mid-run; prove weekly cap is strictly enforced via PostgreSQL."""
        # Create 25 existing committed actions in PostgreSQL
        for i in range(HARD_WEEKLY_APPLICATION_CEILING):
            AgentAction.objects.create(
                run=self.run,
                user=self.user,
                job=self.jobs[i],
                agent_type="auto_apply",
                action_type="auto_apply_auto_submit",
                status="auto_executed",
                executed=True,
                created_at=timezone.now() - timedelta(days=2),
            )

        # Mock Redis crashing with ConnectionError whenever cache is accessed
        with patch("django.core.cache.cache.get", side_effect=redis.exceptions.ConnectionError("Redis connection refused")):
            with patch("django.core.cache.cache.set", side_effect=redis.exceptions.ConnectionError("Redis connection refused")):
                # Assert PostgreSQL authoritative check returns reached
                self.assertEqual(get_weekly_application_count(self.user.id), 25)
                self.assertTrue(check_weekly_cap_reached(self.user.id))
                self.assertFalse(check_weekly_ceiling(self.user))

                # Run graph eligibility node under Redis outage
                state = {"user_id": self.user.id, "run_id": self.run.id}
                caps_res = check_eligibility_caps_node(state)
                self.assertEqual(caps_res["remaining_quota"], 0)
                self.assertEqual(len(caps_res["eligible_jobs"]), 0)

                # Ensure count in PostgreSQL has not bypassed 25
                count = AgentAction.objects.filter(
                    user=self.user,
                    agent_type="auto_apply",
                    status__in=["approved", "auto_executed"],
                ).count()
                self.assertEqual(count, 25)

    def test_daily_cap_enforced_in_postgres_when_redis_dies(self):
        """Simulate Redis down; prove daily cap of 3 strictly stops new submissions."""
        for i in range(3):
            AgentAction.objects.create(
                run=self.run,
                user=self.user,
                job=self.jobs[i],
                agent_type="auto_apply",
                action_type="auto_apply_auto_submit",
                status="auto_executed",
                executed=True,
            )

        with patch("django.core.cache.cache.get", side_effect=redis.exceptions.ConnectionError("Redis down")):
            self.assertEqual(count_applications_today(self.user), 3)
            state = {"user_id": self.user.id, "run_id": self.run.id}
            caps_res = check_eligibility_caps_node(state)
            self.assertEqual(caps_res["remaining_quota"], 0)

    def test_double_apply_prevention(self):
        """Prove that attempting to submit an application twice for the same job is strictly rejected/deduplicated."""
        job = self.jobs[0]
        action1 = create_or_submit_application(
            user=self.user,
            job=job,
            cover_letter="Cover letter 1",
            score=90,
            mode="auto_submit",
            run=self.run,
        )
        self.assertIsNotNone(action1.id)

        # Attempting second creation for same job
        action2 = create_or_submit_application(
            user=self.user,
            job=job,
            cover_letter="Cover letter 2 updated",
            score=92,
            mode="auto_submit",
            run=self.run,
        )
        # Must update/return same record, not create duplicate
        self.assertEqual(action1.id, action2.id)

        # Total applications for candidate & job in DB must be exactly 1
        apps = Application.objects.filter(candidate=self.user, job=job)
        self.assertEqual(apps.count(), 1)
        actions = AgentAction.objects.filter(user=self.user, job=job, agent_type="auto_apply")
        self.assertEqual(actions.count(), 1)

    def test_double_email_prevention(self):
        """Prove that retrying notify_candidate_batch never sends duplicate emails."""
        job = self.jobs[0]
        action = create_or_submit_application(
            user=self.user,
            job=job,
            cover_letter="Cover letter",
            score=95,
            mode="auto_submit",
            run=self.run,
        )

        mail.outbox.clear()

        # First notification
        notify_candidate_batch(self.user, [action], [])
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Auto-Apply: 1 Applications Processed", mail.outbox[0].subject)

        # Reload action from DB
        action.refresh_from_db()
        self.assertTrue(action.payload.get("email_notified"))

        # Second notification attempt (e.g. Celery task retry mid-run)
        notify_candidate_batch(self.user, [action], [])
        # Outbox length must remain 1 - no second email sent!
        self.assertEqual(len(mail.outbox), 1)
