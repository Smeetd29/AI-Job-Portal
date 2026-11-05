from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework import status

from users.models import User, RecruiterProfile
from jobs.models import Job
from application.models import Application
from agents.models import InterviewSlotProposal, Interview
from agents.tools import (
    get_recruiter_calendar_slots,
    rank_slots,
    book_interview,
)
from agents.graph import execute_scheduling_agent

class SchedulingAgentTestCase(TestCase):
    def setUp(self):
        self.recruiter = User.objects.create_user(username="rec_sched", email="rec@mail.com", password="pass")
        self.recruiter_profile = RecruiterProfile.objects.create(
            user=self.recruiter, company_name="Apex Global"
        )
        self.candidate = User.objects.create_user(username="cand_sched", email="cand@mail.com", password="pass")
        self.job = Job.objects.create(
            recruiter=self.recruiter,
            title="Senior Staff Engineer",
            pay_amount=160000,
            category="Engineering",
            description="Staff engineering role",
        )
        self.application = Application.objects.create(
            job=self.job,
            candidate=self.candidate,
            full_name="Alex Candidate",
            email="cand@mail.com",
            graduation_year=2024,
            status="SHORTLISTED",
        )
        self.client = APIClient()

    def test_get_calendar_slots_and_rank(self):
        slots = get_recruiter_calendar_slots(self.recruiter)
        self.assertGreaterEqual(len(slots), 3)

        ranked = rank_slots(slots, "Alex Candidate", "Senior Staff Engineer")
        self.assertEqual(len(ranked), 3)

    def test_execute_scheduling_agent(self):
        result = execute_scheduling_agent(self.application.id, trigger="event")
        self.assertNotIn("error", result)

        proposal = InterviewSlotProposal.objects.filter(application=self.application).first()
        self.assertIsNotNone(proposal)
        self.assertEqual(proposal.status, "pending")
        self.assertEqual(len(proposal.proposed_slots), 3)
        self.assertTrue(len(proposal.magic_token) > 20)

    def test_public_slot_detail_and_confirm_booking(self):
        result = execute_scheduling_agent(self.application.id, trigger="event")
        proposal = InterviewSlotProposal.objects.get(id=result["proposal_id"])
        token = proposal.magic_token

        url_detail = reverse("scheduling-slot-detail", kwargs={"magic_token": token})
        res_detail = self.client.get(url_detail)
        self.assertEqual(res_detail.status_code, status.HTTP_200_OK)
        self.assertEqual(res_detail.data["job_title"], "Senior Staff Engineer")
        self.assertEqual(len(res_detail.data["proposed_slots"]), 3)

        chosen_slot = res_detail.data["proposed_slots"][0]["datetime"]
        url_confirm = reverse("scheduling-confirm", kwargs={"magic_token": token})
        res_confirm = self.client.post(url_confirm, {"chosen_slot": chosen_slot})
        self.assertEqual(res_confirm.status_code, status.HTTP_200_OK)

        proposal.refresh_from_db()
        self.assertEqual(proposal.status, "confirmed")

        interview = Interview.objects.filter(application=self.application).first()
        self.assertIsNotNone(interview)
        self.assertTrue(interview.meeting_link.startswith("https://meet.careerconnect.com/"))

    def test_expired_proposal_cannot_be_booked(self):
        result = execute_scheduling_agent(self.application.id, trigger="event")
        proposal = InterviewSlotProposal.objects.get(id=result["proposal_id"])

        proposal.created_at = timezone.now() - timedelta(hours=73)
        proposal.save(update_fields=["created_at"])

        slot = proposal.proposed_slots[0]["datetime"]
        with self.assertRaises(ValueError):
            book_interview(proposal, slot)
