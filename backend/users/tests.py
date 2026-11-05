import tempfile
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework import status
from rest_framework.test import APIClient

from jobs.models import Job
from users.models import CandidateProfile

User = get_user_model()

from django.core.cache import cache

class UserAuthTests(TestCase):

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.candidate_user = User.objects.create_user(
            username="testcandidate",
            email="candidate@example.com",
            password="SecurePassword123!",
            is_candidate=True,
        )
        self.recruiter_user = User.objects.create_user(
            username="testrecruiter",
            email="recruiter@example.com",
            password="SecurePassword123!",
            is_recruiter=True,
        )

    def test_candidate_signup_success(self):
        payload = {
            "username": "newcandidate",
            "email": "newcand@example.com",
            "password": "StrongPassword987!",
            "role": "candidate",
        }
        response = self.client.post("/api/signup/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(username="newcandidate").exists())
        user = User.objects.get(username="newcandidate")
        self.assertTrue(user.is_candidate)
        self.assertTrue(hasattr(user, "candidate_profile"))

    def test_recruiter_signup_success(self):
        payload = {
            "username": "newrecruiter",
            "email": "newrec@example.com",
            "password": "StrongPassword987!",
            "role": "recruiter",
        }
        response = self.client.post("/api/signup/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="newrecruiter")
        self.assertTrue(user.is_recruiter)
        self.assertTrue(hasattr(user, "recruiter_profile"))

    def test_signup_fails_weak_password_short(self):
        payload = {
            "username": "weakuser",
            "email": "weak@example.com",
            "password": "123",
            "role": "candidate",
        }
        response = self.client.post("/api/signup/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_signup_fails_purely_numeric_password(self):
        payload = {
            "username": "numericuser",
            "email": "num@example.com",
            "password": "12345678901234",
            "role": "candidate",
        }
        response = self.client.post("/api/signup/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", response.data)

    def test_signup_fails_invalid_role(self):
        payload = {
            "username": "badroleuser",
            "email": "badrole@example.com",
            "password": "StrongPassword987!",
            "role": "admin",
        }
        response = self.client.post("/api/signup/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", response.data)

    @override_settings(
        PILOT_INVITE_ONLY=True,
        PILOT_INVITED_EMAILS=frozenset({"invited@example.com"}),
    )
    def test_pilot_signup_requires_invited_email(self):
        response = self.client.post(
            "/api/signup/",
            {
                "username": "notinvited",
                "email": "other@example.com",
                "password": "StrongPassword987!",
                "role": "candidate",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", response.data)
        self.assertFalse(User.objects.filter(username="notinvited").exists())

    @override_settings(
        PILOT_INVITE_ONLY=True,
        PILOT_INVITED_EMAILS=frozenset({"invited@example.com"}),
    )
    def test_pilot_signup_accepts_invited_email_case_insensitively(self):
        response = self.client.post(
            "/api/signup/",
            {
                "username": "invitedcandidate",
                "email": "Invited@Example.com",
                "password": "StrongPassword987!",
                "role": "candidate",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(
            User.objects.get(username="invitedcandidate").email.casefold(),
            "invited@example.com",
        )

    def test_login_success(self):
        payload = {
            "username": "testcandidate",
            "password": "SecurePassword123!",
        }
        response = self.client.post("/api/login/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], "testcandidate")

    def test_login_invalid_credentials(self):
        payload = {
            "username": "testcandidate",
            "password": "WrongPassword!",
        }
        response = self.client.post("/api/login/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("error", response.data)

    @override_settings(
        PILOT_INVITE_ONLY=True,
        PILOT_INVITED_EMAILS=frozenset({"invited@example.com"}),
    )
    def test_pilot_login_rejects_existing_non_invited_account(self):
        response = self.client.post(
            "/api/login/",
            {
                "username": "testcandidate",
                "password": "SecurePassword123!",
            },
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn("error", response.data)

    def test_logout(self):
        self.client.force_authenticate(user=self.candidate_user)
        response = self.client.post("/api/logout/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "Logged out successfully")

    def test_csrf_token_endpoint(self):
        response = self.client.get("/api/csrf/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

class UserProfileTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.candidate = User.objects.create_user(
            username="profile_cand",
            email="cand@test.com",
            password="SecurePassword123!",
            is_candidate=True,
        )
        self.recruiter = User.objects.create_user(
            username="profile_rec",
            email="rec@test.com",
            password="SecurePassword123!",
            is_recruiter=True,
        )

    def test_profile_requires_authentication(self):
        response = self.client.get("/api/profile/")
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_unauthenticated_profile_update_rejected(self):
        response = self.client.patch("/api/profile/", {"email": "hacked@test.com"}, format="json")
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_unauthenticated_resume_update_rejected(self):
        response = self.client.post("/api/profile/resume/", {"skills": "Python"}, format="json")
        self.assertIn(response.status_code, [status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN])

    def test_get_authenticated_profile(self):
        self.client.force_authenticate(user=self.candidate)
        response = self.client.get("/api/profile/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "cand@test.com")

    def test_update_profile(self):
        self.client.force_authenticate(user=self.candidate)
        response = self.client.patch("/api/profile/", {"email": "updated@test.com"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.candidate.refresh_from_db()
        self.assertEqual(self.candidate.email, "updated@test.com")

    def test_cannot_elevate_privileges_via_profile_update(self):
        self.client.force_authenticate(user=self.candidate)
        response = self.client.patch("/api/profile/", {"is_recruiter": True}, format="json")
        self.candidate.refresh_from_db()
        self.assertFalse(self.candidate.is_recruiter)


class ResumeInsightsEndpointTests(TestCase):
    def setUp(self):
        cache.clear()
        self.media_directory = tempfile.TemporaryDirectory()
        self.settings_override = override_settings(MEDIA_ROOT=self.media_directory.name)
        self.settings_override.enable()
        self.addCleanup(self.settings_override.disable)
        self.addCleanup(self.media_directory.cleanup)
        self.client = APIClient()
        self.candidate = User.objects.create_user(
            username="insight_candidate",
            email="insight_candidate@test.com",
            password="SecurePassword123!",
            is_candidate=True,
        )
        self.profile, _ = CandidateProfile.objects.get_or_create(user=self.candidate)
        self.profile.resume.save(
            "resume.txt",
            SimpleUploadedFile(
                "resume.txt",
                b"Skills: Python, Django\nBuilt REST APIs with Django.",
                content_type="text/plain",
            ),
        )
        self.recruiter = User.objects.create_user(
            username="insight_recruiter",
            email="insight_recruiter@test.com",
            password="SecurePassword123!",
            is_recruiter=True,
        )

    @patch("users.views.build_resume_insights")
    def test_candidate_can_request_and_cache_own_resume_insights(self, build_insights):
        build_insights.return_value = {
            "verified_facts": {"skills": [{"skill": "Django"}]},
            "generation_status": "deterministic_fallback",
            "model": None,
        }
        self.client.force_authenticate(user=self.candidate)

        first = self.client.post("/api/profile/insights/", {}, format="json")
        second = self.client.post("/api/profile/insights/", {}, format="json")

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertFalse(first.data["cached"])
        self.assertTrue(second.data["cached"])
        build_insights.assert_called_once()
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.resume_facts["facts"]["skills"][0]["skill"], "Django")

    def test_recruiter_cannot_request_candidate_resume_insights(self):
        self.client.force_authenticate(user=self.recruiter)
        response = self.client.post("/api/profile/insights/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
