from __future__ import annotations

import io
from pathlib import Path
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from application.ai.autofill import (
    AutofillResult,
    ConfidenceLevel,
    ResumeAutofillService,
)
from application.ai.autofill import (
    validate_cgpa,
    validate_degree,
    validate_email,
    validate_github_url,
    validate_graduation_year,
    validate_linkedin_url,
    validate_phone,
)

User = get_user_model()

class ResumeAutofillRegressionTests(TestCase):

    def setUp(self):
        self.service = ResumeAutofillService()
        self.pdf_path = Path(__file__).resolve().parents[4] / "media" / "application_resumes" / "Smeet_CV.pdf"

    def test_smeet_pdf_autofill_end_to_end(self):
        if not self.pdf_path.exists():
            self.skipTest(f"Resume PDF not found at {self.pdf_path}")

        result = self.service.process(file_source=str(self.pdf_path))
        data = result.autofill_data
        form = result.mapped_form_data

        self.assertEqual(data.contact.email.value, "smeetdalal29@gmail.com")
        self.assertIn("79775", data.contact.phone.value)
        self.assertIn("linkedin.com/in/smeet-dalal", data.contact.linkedin.value)
        self.assertIn("github.com/Smeetd29", data.contact.github.value)

        self.assertIn("Sanghavi", data.education.institution.value)
        self.assertEqual(data.education.graduation_year.value, 2028)
        self.assertEqual(data.education.cgpa.value, "9.45")
        self.assertEqual(data.education.academic_level.value, "Bachelor")

        self.assertEqual(len(data.professional_experience), 0)
        self.assertEqual(data.years_professional_experience.value, 0.0)

        self.assertGreaterEqual(len(data.projects), 1)

        self.assertEqual(form.get("email"), "smeetdalal29@gmail.com")
        self.assertEqual(form.get("graduation_year"), 2028)
        self.assertEqual(form.get("overall_grade"), "9.45")
        self.assertEqual(form.get("academic_level"), "Bachelor")

    def test_education_dates_never_become_work_experience(self):
        text = (
            "Alex Smith\nalex@example.com\n\n"
            "EDUCATION\n"
            "B.Tech in Computer Science\n"
            "ABC Institute of Technology\n"
            "2024 - 2028 | CGPA: 8.90\n\n"
            "High School\n"
            "St. Mary's School\n"
            "2009 - 2024\n"
        )
        fake_file = SimpleUploadedFile("edu.txt", text.encode("utf-8"))
        result = self.service.process(file_source=fake_file)

        self.assertEqual(result.autofill_data.years_professional_experience.value, 0.0)
        self.assertEqual(len(result.autofill_data.professional_experience), 0)
        self.assertEqual(result.mapped_form_data.get("graduation_year"), 2028)

    def test_college_committee_never_becomes_employment(self):
        text = (
            "John Doe\njohn@example.com\n\n"
            "EXPERIENCE\n"
            "Unicode - College Technical Committee\n"
            "Technical Member | 2024 - Present\n"
            "Organized student coding workshops and campus hackathons.\n"
        )
        fake_file = SimpleUploadedFile("club.txt", text.encode("utf-8"))
        result = self.service.process(file_source=fake_file)

        self.assertEqual(len(result.autofill_data.professional_experience), 0)
        self.assertEqual(result.autofill_data.years_professional_experience.value, 0.0)

    def test_projects_segregated_from_professional_experience(self):
        text = (
            "Jane Doe\njane@example.com\n\n"
            "PROJECTS\n"
            "CampusFlow - College Event Platform | Django, React Native, PostgreSQL\n"
            "Built end-to-end event registration workflow handling 1,500 attendees.\n"
        )
        fake_file = SimpleUploadedFile("proj.txt", text.encode("utf-8"))
        result = self.service.process(file_source=fake_file)

        self.assertGreaterEqual(len(result.autofill_data.projects), 1)
        self.assertEqual(result.autofill_data.projects[0].title, "CampusFlow - College Event Platform")
        self.assertEqual(len(result.autofill_data.professional_experience), 0)

    def test_validators_unit_cases(self):
        self.assertTrue(validate_email("user@domain.com")[0])
        self.assertFalse(validate_email("invalid-email")[0])

        self.assertTrue(validate_phone("+91 79775 85157")[0])
        self.assertFalse(validate_phone("123")[0])

        self.assertTrue(validate_linkedin_url("https://www.linkedin.com/in/smeet-dalal")[0])
        self.assertFalse(validate_linkedin_url("https://facebook.com/profile")[0])
        self.assertTrue(validate_github_url("github.com/Smeetd29")[0])

        valid, val, sys_name = validate_cgpa("CGPA: 9.45/10")
        self.assertTrue(valid)
        self.assertEqual(val, "9.45")
        self.assertEqual(sys_name, "CGPA")

        self.assertTrue(validate_graduation_year(2028)[0])
        self.assertFalse(validate_graduation_year(1850)[0])

        self.assertEqual(validate_degree("B.Tech in Computer Science")[2], "Bachelor")
        self.assertEqual(validate_degree("Master of Science")[2], "Master")
        self.assertEqual(validate_degree("Ph.D in AI")[2], "PhD")

    def test_profile_priority_and_conflict_detection(self):
        user = User.objects.create_user(
            username="testcandidate",
            email="profile@example.com",
            first_name="Verified",
            last_name="User",
            is_candidate=True,
        )
        from users.models import CandidateProfile
        CandidateProfile.objects.create(user=user, phone="+1 555-0199")

        resume_text = (
            "Resume Name\n"
            "resume_diff@example.com\n"
            "+91 99999 88888\n\n"
            "SKILLS\nPython, Django\n"
        )
        fake_file = SimpleUploadedFile("resume.txt", resume_text.encode("utf-8"))
        result = self.service.process(file_source=fake_file, candidate_user=user)

        self.assertEqual(result.autofill_data.contact.email.value, "profile@example.com")
        self.assertEqual(result.autofill_data.contact.full_name.value, "Verified User")
        self.assertEqual(result.autofill_data.contact.phone.value, "+1 555-0199")

        self.assertIn("email", result.conflicts)
        self.assertEqual(result.conflicts["email"]["resume_value"], "resume_diff@example.com")
        self.assertIn("full_name", result.conflicts)

    def test_empty_and_missing_sections_safely_handled(self):
        fake_file = SimpleUploadedFile("empty.txt", b"   \n  \n")
        result = self.service.process(file_source=fake_file)

        self.assertIsInstance(result, AutofillResult)
        self.assertEqual(result.autofill_data.contact.email.confidence_level, ConfidenceLevel.UNKNOWN)
        self.assertEqual(result.mapped_form_data, {})

class AutofillApiEndpointTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.candidate = User.objects.create_user(
            username="candidate_api",
            email="candidate_api@example.com",
            password="Password123!",
            is_candidate=True,
        )
        from users.models import CandidateProfile
        self.profile = CandidateProfile.objects.create(user=self.candidate)

        self.recruiter = User.objects.create_user(
            username="recruiter_api",
            email="recruiter_api@example.com",
            password="Password123!",
            is_recruiter=True,
        )

    def test_autofill_endpoint_success_with_file_upload(self):
        self.client.force_authenticate(user=self.candidate)
        content = (
            "Smeet Dalal\n"
            "smeet@example.com\n"
            "+91 79775 85157\n\n"
            "EDUCATION\n"
            "B.Tech in Computer Science\n"
            "DJ Sanghvi College of Engineering\n"
            "2024 - 2028 | CGPA: 9.45\n\n"
            "SKILLS\n"
            "Python, Django, Docker, PostgreSQL\n"
        )
        resume_file = SimpleUploadedFile("cv.txt", content.encode("utf-8"), content_type="text/plain")

        response = self.client.post("/api/applications/autofill/", {"resume": resume_file}, format="multipart")
        self.assertEqual(response.status_code, 200)

        data = response.json()
        self.assertIn("mapped_form_data", data)
        self.assertIn("field_provenance", data)
        form = data["mapped_form_data"]
        self.assertEqual(form.get("university_name"), "DJ Sanghvi College of Engineering")
        self.assertEqual(form.get("graduation_year"), 2028)
        self.assertEqual(form.get("overall_grade"), "9.45")

    def test_autofill_requires_candidate_permission(self):
        self.client.force_authenticate(user=self.recruiter)
        resume_file = SimpleUploadedFile("cv.txt", b"content", content_type="text/plain")
        response = self.client.post("/api/applications/autofill/", {"resume": resume_file}, format="multipart")
        self.assertEqual(response.status_code, 403)
