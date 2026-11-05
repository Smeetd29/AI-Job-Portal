from __future__ import annotations

import threading
from typing import List
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.test import TransactionTestCase
from django.db import connection
from agents.models import AgentAction, AgentRun, AutoApplySettings
from agents.tools import create_or_submit_application, send_action_email
from agents.guardrails import HARD_WEEKLY_APPLICATION_CEILING, get_weekly_application_count
from jobs.models import Job
from users.models import CandidateProfile, RecruiterProfile

User = get_user_model()

class TestConcurrencyAndEmailIdempotency(TransactionTestCase):
    """
    Validates concurrency safety and at-most-once email delivery:
    1. Cap Race: Exactly one thread succeeds when two concurrent workers run at 24/25.
    2. Email Idempotency: Claim-then-send prevents duplicate emails on retry / crash.
    """

    def setUp(self):
        # Prevent heavy background neural reindexing during transactional unit test
        self.faiss_patcher = patch("application.ai.tasks.rebuild_faiss_index_task.delay")
        self.faiss_patcher.start()
        self.addCleanup(self.faiss_patcher.stop)

        self.screening_patcher = patch("agents.tasks.run_screening_agent.delay")
        self.screening_patcher.start()
        self.addCleanup(self.screening_patcher.stop)

        self.candidate = User.objects.create_user(
            username="concurrent_cand",
            email="cand@concurrent.com",
            password="pass",
            is_candidate=True,
        )
        CandidateProfile.objects.create(user=self.candidate, skills="Python, Django")
        self.settings = AutoApplySettings.objects.create(
            user=self.candidate,
            enabled=True,
            daily_cap=50,
            mode="auto_submit",
        )
        self.run = AgentRun.objects.create(
            agent_type="auto_apply",
            user=self.candidate,
            trigger="manual",
        )

        self.recruiter = User.objects.create_user(
            username="concurrent_rec",
            email="rec@concurrent.com",
            password="pass",
            is_recruiter=True,
        )
        RecruiterProfile.objects.create(user=self.recruiter, company_name="RaceCorp")

        self.job1 = Job.objects.create(
            title="Backend Dev 1",
            description="Python",
            recruiter=self.recruiter,
            pay_amount=130000.0,
            category="Engineering",
            is_active=True,
        )
        self.job2 = Job.objects.create(
            title="Backend Dev 2",
            description="Python",
            recruiter=self.recruiter,
            pay_amount=135000.0,
            category="Engineering",
            is_active=True,
        )

    def test_cap_race_concurrency_at_24_two_threads(self):
        """
        Pre-seed 24 actions (under cap).
        Spawn 2 concurrent threads attempting to submit application #25.
        With select_for_update() row lock, exactly ONE succeeds and one fails.
        """
        for i in range(24):
            AgentAction.objects.create(
                run=self.run,
                user=self.candidate,
                agent_type="auto_apply",
                action_type="auto_apply_auto_submit",
                status="auto_executed",
                executed=True,
            )

        initial_count = get_weekly_application_count(self.candidate.id)
        self.assertEqual(initial_count, 24)

        successes: List[AgentAction] = []
        errors: List[Exception] = []

        def worker(job: Job):
            max_attempts = 10
            for attempt in range(max_attempts):
                try:
                    action = create_or_submit_application(
                        user=self.candidate,
                        job=job,
                        cover_letter="Cover letter body",
                        score=90,
                        mode="auto_submit",
                        run=self.run,
                    )
                    successes.append(action)
                    break
                except Exception as e:
                    # In SQLite without true row-level locks, reader-upgrade contention raises table locked.
                    # Back off and retry so the competing thread can complete and the ceiling will be hit.
                    if "locked" in str(e).lower() and attempt < max_attempts - 1:
                        import time
                        time.sleep(0.05 * (attempt + 1))
                        continue
                    errors.append(e)
                    break
                finally:
                    connection.close()

        t1 = threading.Thread(target=worker, args=(self.job1,))
        t2 = threading.Thread(target=worker, args=(self.job2,))

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Exactly one thread must succeed and one must fail
        self.assertEqual(len(successes), 1, f"Expected exactly 1 success, got {len(successes)}")
        self.assertEqual(len(errors), 1, f"Expected exactly 1 failure, got {len(errors)}")
        # On Postgres, select_for_update serializes workers so worker 2 sees count=25 and raises ValueError(ceiling).
        # On SQLite, file/table-level locking rejects concurrent writes with OperationalError("database table is locked").
        # In both engines, exactly one transaction succeeds and the other is rejected.
        err_msg = str(errors[0]).lower()
        self.assertTrue(
            "ceiling" in err_msg or "locked" in err_msg,
            f"Expected cap ceiling or db lock rejection, got: {errors[0]}",
        )

        # Total count must be exactly 25 (ceiling), never 26
        final_count = get_weekly_application_count(self.candidate.id)
        self.assertEqual(final_count, HARD_WEEKLY_APPLICATION_CEILING)

    def test_email_claim_then_send_idempotency_and_crash_simulation(self):
        """
        Verifies atomic claim-then-send idempotency:
        1. Action starts with email_state=None -> claimed & sent successfully.
        2. Second send attempt on already sent action is rejected (no second email).
        3. Simulated crash (state='sending') -> retry does not duplicate email.
        """
        action = AgentAction.objects.create(
            run=self.run,
            user=self.candidate,
            job=self.job1,
            agent_type="auto_apply",
            action_type="auto_apply_auto_submit",
            status="auto_executed",
            executed=True,
            email_state=None,
        )

        # 1. First send: transitions None -> 'sending' -> 'sent'
        first_send = send_action_email(
            action=action,
            template="test_template",
            to="candidate@example.com",
            context={"subject": "Test Notification", "message": "First message"},
        )
        self.assertTrue(first_send)

        action.refresh_from_db()
        self.assertEqual(action.email_state, "sent")

        # 2. Second send attempt: already 'sent' -> must return False and NOT send again
        second_send = send_action_email(
            action=action,
            template="test_template",
            to="candidate@example.com",
            context={"subject": "Duplicate Notification", "message": "Second message"},
        )
        self.assertFalse(second_send)

        # 3. Simulated crash between send and mark:
        # Worker claimed row (email_state='sending') but crashed before marking 'sent'
        crashed_action = AgentAction.objects.create(
            run=self.run,
            user=self.candidate,
            job=self.job2,
            agent_type="auto_apply",
            action_type="auto_apply_auto_submit",
            status="auto_executed",
            executed=True,
            email_state="sending",  # Left in 'sending' by crashed worker
        )

        # A retry worker encounters 'sending' state
        retry_send = send_action_email(
            action=crashed_action,
            template="test_template",
            to="candidate@example.com",
            context={"subject": "Retry Notification", "message": "Retry message"},
        )
        self.assertFalse(retry_send, "Retry must not send duplicate email for crashed worker (at-most-once)")
