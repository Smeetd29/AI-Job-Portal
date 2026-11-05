from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from .models import Job

User = get_user_model()

class JobCRUDAndOwnershipTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.recruiter_a = User.objects.create_user(
            username="recruiter_a",
            email="a@example.com",
            password="SecurePassword123!",
            is_recruiter=True,
        )
        self.recruiter_b = User.objects.create_user(
            username="recruiter_b",
            email="b@example.com",
            password="SecurePassword123!",
            is_recruiter=True,
        )
        self.candidate = User.objects.create_user(
            username="candidate_user",
            email="cand@example.com",
            password="SecurePassword123!",
            is_candidate=True,
        )

        self.job_a = Job.objects.create(
            recruiter=self.recruiter_a,
            title="Backend Engineer",
            category="Engineering",
            job_type="Full Time",
            location_type="Remote",
            pay_amount=90000,
            pay_mode="Monthly",
            description="Build robust APIs in Python and Django.",
            is_active=True,
        )

    def test_anonymous_can_list_jobs(self):
        response = self.client.get("/jobs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_anonymous_cannot_create_job(self):
        payload = {"title": "New Job", "description": "Test", "category": "Engineering"}
        response = self.client.post("/jobs/", payload, format="json")
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_anonymous_cannot_update_or_delete_job(self):
        patch_res = self.client.patch(f"/jobs/{self.job_a.id}/", {"title": "Anon Hack"}, format="json")
        self.assertIn(patch_res.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])
        del_res = self.client.delete(f"/jobs/{self.job_a.id}/")
        self.assertIn(del_res.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_candidate_cannot_create_job(self):
        self.client.force_authenticate(user=self.candidate)
        payload = {"title": "New Job", "description": "Test", "category": "Engineering"}
        response = self.client.post("/jobs/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_candidate_cannot_update_or_delete_job(self):
        self.client.force_authenticate(user=self.candidate)
        patch_res = self.client.patch(f"/jobs/{self.job_a.id}/", {"title": "Cand Hack"}, format="json")
        self.assertEqual(patch_res.status_code, status.HTTP_403_FORBIDDEN)
        del_res = self.client.delete(f"/jobs/{self.job_a.id}/")
        self.assertEqual(del_res.status_code, status.HTTP_403_FORBIDDEN)

    def test_recruiter_can_create_job(self):
        self.client.force_authenticate(user=self.recruiter_a)
        payload = {
            "title": "Frontend Engineer",
            "category": "Engineering",
            "job_type": "Full Time",
            "location_type": "Remote",
            "pay_amount": 85000,
            "pay_mode": "Monthly",
            "description": "React and TypeScript experience required.",
        }
        response = self.client.post("/jobs/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        new_job = Job.objects.get(id=response.data["id"])
        self.assertEqual(new_job.recruiter, self.recruiter_a)

    def test_recruiter_cannot_update_another_recruiters_job(self):
        self.client.force_authenticate(user=self.recruiter_b)
        response = self.client.patch(
            f"/jobs/{self.job_a.id}/",
            {"title": "Hacked Title"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.job_a.refresh_from_db()
        self.assertEqual(self.job_a.title, "Backend Engineer")

    def test_recruiter_cannot_put_update_another_recruiters_job(self):
        self.client.force_authenticate(user=self.recruiter_b)
        full_payload = {
            "title": "Hacked Full Title",
            "description": "Malicious override",
            "category": "Engineering",
            "job_type": "Full Time",
            "location_type": "Remote",
            "pay_amount": 1000,
            "pay_mode": "Monthly",
        }
        response = self.client.put(f"/jobs/{self.job_a.id}/", full_payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.job_a.refresh_from_db()
        self.assertEqual(self.job_a.title, "Backend Engineer")

    def test_recruiter_cannot_delete_another_recruiters_job(self):
        self.client.force_authenticate(user=self.recruiter_b)
        response = self.client.delete(f"/jobs/{self.job_a.id}/")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Job.objects.filter(id=self.job_a.id).exists())

    def test_recruiter_can_update_own_job(self):
        self.client.force_authenticate(user=self.recruiter_a)
        response = self.client.patch(
            f"/jobs/{self.job_a.id}/",
            {"title": "Lead Backend Engineer"},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.job_a.refresh_from_db()
        self.assertEqual(self.job_a.title, "Lead Backend Engineer")

    def test_recruiter_can_delete_own_job(self):
        self.client.force_authenticate(user=self.recruiter_a)
        response = self.client.delete(f"/jobs/{self.job_a.id}/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Job.objects.filter(id=self.job_a.id).exists())

class JobFilterAndSaveTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.recruiter_a = User.objects.create_user(
            username="recruiter_main",
            email="rec_main@example.com",
            password="SecurePassword123!",
            is_recruiter=True,
        )
        self.recruiter_b = User.objects.create_user(
            username="recruiter_second",
            email="rec_sec@example.com",
            password="SecurePassword123!",
            is_recruiter=True,
        )
        self.candidate = User.objects.create_user(
            username="candidate_main",
            email="cand_main@example.com",
            password="SecurePassword123!",
            is_candidate=True,
        )

        now = timezone.now()
        self.active_job_a = Job.objects.create(
            recruiter=self.recruiter_a,
            title="Python Cloud Engineer",
            category="Engineering",
            job_type="Full Time",
            location_type="Remote",
            pay_amount=100000,
            pay_mode="Monthly",
            description="Python, AWS, and Docker.",
            is_active=True,
            expires_at=now + timedelta(days=30),
        )
        self.active_job_b = Job.objects.create(
            recruiter=self.recruiter_b,
            title="DevOps Specialist",
            category="Engineering",
            job_type="Full Time",
            location_type="Remote",
            pay_amount=110000,
            pay_mode="Monthly",
            description="Kubernetes, CI/CD, Terraform.",
            is_active=True,
            expires_at=now + timedelta(days=30),
        )
        self.expired_job = Job.objects.create(
            recruiter=self.recruiter_a,
            title="Old Job",
            category="Engineering",
            job_type="Full Time",
            location_type="Remote",
            pay_amount=50000,
            pay_mode="Monthly",
            description="Expired position.",
            is_active=True,
            expires_at=now - timedelta(days=1),
        )

    def test_expired_jobs_excluded_from_public_list(self):
        response = self.client.get("/jobs/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        job_ids = [j["id"] for j in response.data]
        self.assertIn(self.active_job_a.id, job_ids)
        self.assertNotIn(self.expired_job.id, job_ids)

    def test_search_jobs(self):
        response = self.client.get("/jobs/?search=Cloud")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["id"], self.active_job_a.id)

    def test_manage_query_isolates_recruiters(self):
        self.client.force_authenticate(user=self.recruiter_a)
        response = self.client.get("/jobs/?manage=true")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        job_ids = [j["id"] for j in response.data]
        self.assertIn(self.active_job_a.id, job_ids)
        self.assertNotIn(self.active_job_b.id, job_ids)

    def test_candidate_save_and_retrieve_job(self):
        self.client.force_authenticate(user=self.candidate)
        save_res = self.client.post("/saved-jobs/", {"job": self.active_job_a.id}, format="json")
        self.assertEqual(save_res.status_code, status.HTTP_201_CREATED)

        list_res = self.client.get("/saved-jobs/")
        self.assertEqual(list_res.status_code, status.HTTP_200_OK)
        self.assertEqual(len(list_res.data), 1)
        self.assertEqual(list_res.data[0]["job"], self.active_job_a.id)

    def test_recruiter_cannot_save_jobs(self):
        self.client.force_authenticate(user=self.recruiter_a)
        save_res = self.client.post("/saved-jobs/", {"job": self.active_job_a.id}, format="json")
        self.assertEqual(save_res.status_code, status.HTTP_403_FORBIDDEN)
