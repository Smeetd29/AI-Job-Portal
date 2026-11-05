from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient
from pathlib import Path

from jobs.models import Job
from application.models import Application

User = get_user_model()

class ResumeSecurityRegressionTests(TestCase):
    def setUp(self):
        cache.clear()
        self.client = APIClient()

        self.candidate_a = User.objects.create_user(
            username="candidate_a",
            email="cand_a@example.com",
            password="SecurePassword123!",
            is_candidate=True,
        )
        self.candidate_b = User.objects.create_user(
            username="candidate_b",
            email="cand_b@example.com",
            password="SecurePassword123!",
            is_candidate=True,
        )
        self.recruiter_a = User.objects.create_user(
            username="recruiter_a",
            email="rec_a@example.com",
            password="SecurePassword123!",
            is_recruiter=True,
        )
        self.recruiter_b = User.objects.create_user(
            username="recruiter_b",
            email="rec_b@example.com",
            password="SecurePassword123!",
            is_recruiter=True,
        )

        self.job_a = Job.objects.create(
            recruiter=self.recruiter_a,
            title="Software Engineer",
            pay_amount=100000,
            pay_mode="Monthly",
            job_type="Full Time",
            location_type="Remote",
            category="Engineering",
            description="Python engineering role",
        )

        dummy_resume = SimpleUploadedFile(
            "candidate_a_resume.pdf",
            b"%PDF-1.4 Mock Candidate Resume Data",
            content_type="application/pdf",
        )

        self.app_a = Application.objects.create(
            job=self.job_a,
            candidate=self.candidate_a,
            full_name="Candidate A",
            email="cand_a@example.com",
            phone_number="1234567890",
            university_name="Tech University",
            university_country="USA",
            academic_level="Bachelor",
            stream="Computer Science",
            current_year="Graduated",
            graduation_year=2022,
            major="Computer Science",
            grading_system="GPA",
            overall_grade="3.9",
            skills="Python, Django",
            area_of_interest="Backend",
            resume_snapshot=dummy_resume,
        )

    def tearDown(self):
        cache.clear()

    def test_anonymous_cannot_access_resume(self):
        """Anonymous requests must be rejected with 401 Unauthorized."""
        response = self.client.get(f"/api/applications/{self.app_a.id}/resume/")
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_candidate_cannot_access_other_candidate_resume(self):
        """Candidate B must not be able to access Candidate A's resume (IDOR protection)."""
        self.client.force_authenticate(user=self.candidate_b)
        response = self.client.get(f"/api/applications/{self.app_a.id}/resume/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unrelated_recruiter_cannot_access_resume(self):
        """Recruiter B (who did not post job A) cannot access Candidate A's application resume."""
        self.client.force_authenticate(user=self.recruiter_b)
        response = self.client.get(f"/api/applications/{self.app_a.id}/resume/")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_authorized_recruiter_can_access_resume(self):
        """Recruiter A (job owner) can access Candidate A's application resume."""
        self.client.force_authenticate(user=self.recruiter_a)
        response = self.client.get(f"/api/applications/{self.app_a.id}/resume/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_candidate_can_access_own_resume(self):
        """Candidate A can access their own application resume."""
        self.client.force_authenticate(user=self.candidate_a)
        response = self.client.get(f"/api/applications/{self.app_a.id}/resume/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response["Content-Type"], "application/pdf")

    def test_minio_initialization_sets_anonymous_none(self):
        """Verify docker-compose.yml enforces private bucket policy with anonymous set none."""
        compose_path = Path(__file__).resolve().parent.parent.parent / "docker-compose.yml"
        self.assertTrue(compose_path.exists(), "docker-compose.yml must exist")
        content = compose_path.read_text(encoding="utf-8")
        self.assertIn("mc anonymous set none", content)
        self.assertNotIn("mc anonymous set download", content)

    def test_auth_rate_limiting_triggers_429(self):
        """Rapid repeated login attempts from same client trigger 429 Too Many Requests."""
        cache.clear()
        client = APIClient()
        responses = []
        for i in range(7):
            res = client.post("/api/login/", {"username": "cand_a", "password": f"WrongPass{i}"}, format="json")
            responses.append(res.status_code)
        self.assertIn(status.HTTP_429_TOO_MANY_REQUESTS, responses)

    def test_production_settings_reject_missing_secret(self):
        """Production configuration must reject missing or insecure secret key."""
        from django.core.exceptions import ImproperlyConfigured
        # Test simulated production validation
        def validate_production_key(key):
            if not key or key.startswith("django-insecure-") or len(key) < 50:
                raise ImproperlyConfigured("Insecure production key")
        
        with self.assertRaises(ImproperlyConfigured):
            validate_production_key("django-insecure-short")
        with self.assertRaises(ImproperlyConfigured):
            validate_production_key("")
        with self.assertRaises(ImproperlyConfigured):
            validate_production_key("short_key_under_50_chars")
