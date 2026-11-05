from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from rest_framework import status
from rest_framework.test import APIClient

from jobs.models import Job
from .models import Application
from .serializers import ApplicationSerializer

User = get_user_model()

class ApplicationSerializerTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='candidate',
            email='candidate@example.com',
            password='SecurePassword123!',
            is_candidate=True,
        )
        self.recruiter = User.objects.create_user(
            username='recruiter',
            email='recruiter@example.com',
            password='SecurePassword123!',
            is_recruiter=True,
        )
        self.job = Job.objects.create(
            recruiter=self.recruiter,
            title='Designer',
            pay_amount=1000,
            pay_mode='Monthly',
            job_type='Full Time',
            location_type='Remote',
            category='Design',
            description='Test job',
        )

    def test_resume_snapshot_is_returned_as_absolute_url(self):
        uploaded_file = SimpleUploadedFile(
            'resume.pdf',
            b'%PDF-1.4 Mock PDF content for test',
            content_type='application/pdf',
        )
        application = Application.objects.create(
            job=self.job,
            candidate=self.user,
            full_name='Candidate',
            email='candidate@example.com',
            phone_number='1234567890',
            university_name='Test University',
            university_country='India',
            academic_level='Bachelor',
            stream='Design',
            current_year='4th',
            graduation_year=2024,
            major='Visual Design',
            grading_system='GPA',
            overall_grade='3.8',
            skills='UI/UX',
            area_of_interest='Design',
            linkedin_profile='https://linkedin.com/in/candidate',
            referral_source='LinkedIn',
            work_authorization_country='India',
            resume_snapshot=uploaded_file,
        )

        request = RequestFactory().get('/')
        serializer = ApplicationSerializer(application, context={'request': request})

        self.assertTrue(serializer.data['resume_snapshot'].startswith('http://testserver'))

class ApplicationAISummarizeTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.recruiter_owner = User.objects.create_user(
            username='rec_owner',
            email='owner@test.com',
            password='SecurePassword123!',
            is_recruiter=True,
        )
        self.recruiter_other = User.objects.create_user(
            username='rec_other',
            email='other@test.com',
            password='SecurePassword123!',
            is_recruiter=True,
        )
        self.candidate = User.objects.create_user(
            username='cand_user',
            email='cand@test.com',
            password='SecurePassword123!',
            is_candidate=True,
        )
        self.job = Job.objects.create(
            recruiter=self.recruiter_owner,
            title='Python Developer',
            pay_amount=90000,
            pay_mode='Monthly',
            job_type='Full Time',
            location_type='Remote',
            category='Engineering',
            description='Requirements: Strong knowledge of Python, Django, and PostgreSQL. 3+ years experience.',
        )

        resume_content = (
            b"Jane Doe\n"
            b"Summary: Experienced software developer with 4 years in Python and Django.\n"
            b"Skills: Python, Django, PostgreSQL, Docker\n"
            b"Experience: Built scalable backend services for 4 years using Django.\n"
            b"Education: Bachelor of Science in Computer Science.\n"
        )
        self.uploaded_resume = SimpleUploadedFile(
            'jane_resume.txt',
            resume_content,
            content_type='text/plain',
        )

        self.application = Application.objects.create(
            job=self.job,
            candidate=self.candidate,
            full_name='Jane Doe',
            email='jane@example.com',
            phone_number='9876543210',
            university_name='State University',
            academic_level='Bachelor',
            graduation_year=2021,
            major='Computer Science',
            skills='Python, Django',
            resume_snapshot=self.uploaded_resume,
        )

    def test_summarize_endpoint_generates_ai_analysis(self):
        self.client.force_authenticate(user=self.recruiter_owner)
        response = self.client.post(f"/applications/{self.application.id}/summarize/", format="json")

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('ai_summary', response.data)
        summary = response.data['ai_summary']

        self.assertIn('match_score', summary)
        self.assertGreaterEqual(summary['match_score'], 0)
        self.assertLessEqual(summary['match_score'], 100)

        self.assertIn('key_skills', summary)
        self.assertIn('matching_points', summary)
        self.assertIn('recommendation', summary)
        self.assertFalse(response.data['cached'])

    def test_summarize_cached_behavior(self):
        self.client.force_authenticate(user=self.recruiter_owner)
        res1 = self.client.post(f"/applications/{self.application.id}/summarize/", format="json")
        self.assertEqual(res1.status_code, status.HTTP_200_OK)

        res2 = self.client.post(f"/applications/{self.application.id}/summarize/", format="json")
        self.assertEqual(res2.status_code, status.HTTP_200_OK)
        self.assertTrue(res2.data['cached'])

    def test_candidate_cannot_access_summarize(self):
        self.client.force_authenticate(user=self.candidate)
        response = self.client.post(f"/applications/{self.application.id}/summarize/", format="json")
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unrelated_recruiter_cannot_access_summarize(self):
        self.client.force_authenticate(user=self.recruiter_other)
        response = self.client.post(f"/applications/{self.application.id}/summarize/", format="json")
        self.assertIn(response.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])


class SoftArchiveApplicantTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.recruiter = User.objects.create_user(
            username='recruiter_archive_test',
            email='rec_archive@test.com',
            password='SecurePassword123!',
            is_recruiter=True,
        )
        self.candidate = User.objects.create_user(
            username='cand_archive_test',
            email='cand_archive@test.com',
            password='SecurePassword123!',
            is_candidate=True,
        )
        self.job = Job.objects.create(
            recruiter=self.recruiter,
            title='Backend Architect',
            pay_amount=150000,
            pay_mode='Monthly',
            job_type='Full Time',
            location_type='Remote',
            category='Engineering',
            description='Test engineering job for soft archive testing.',
        )
        self.uploaded_resume = SimpleUploadedFile(
            'test_resume.txt',
            b'Test resume content for applicant archive tests.',
            content_type='text/plain',
        )
        self.application = Application.objects.create(
            job=self.job,
            candidate=self.candidate,
            full_name='Test Candidate',
            email='cand_archive@test.com',
            phone_number='1234567890',
            university_name='Tech University',
            academic_level='Master',
            graduation_year=2022,
            major='Computer Science',
            skills='Python, Django',
            resume_snapshot=self.uploaded_resume,
        )

    def _get_jobs_list(self, res):
        if isinstance(res.data, dict):
            return res.data.get('results', [])
        return res.data

    def _get_apps_list(self, res):
        if isinstance(res.data, dict):
            return res.data.get('results', [])
        return res.data

    def test_dry_run_changes_nothing(self):
        from django.core.management import call_command
        import io
        out = io.StringIO()
        call_command('reset_test_applicants', dry_run=True, stdout=out)
        self.application.refresh_from_db()
        self.assertIsNone(self.application.archived_at)
        self.assertEqual(self.application.archive_batch, '')

    def test_row_count_is_unchanged_after_archive(self):
        from django.core.management import call_command
        import io
        count_before = Application.objects.count()
        out = io.StringIO()
        call_command('reset_test_applicants', confirm=True, stdout=out)
        count_after = Application.objects.count()
        self.assertEqual(count_before, count_after)

        self.application.refresh_from_db()
        self.assertIsNotNone(self.application.archived_at)
        self.assertTrue(self.application.archive_batch.startswith('batch_'))

    def test_archived_records_are_hidden_from_recruiter_dashboard(self):
        from django.core.management import call_command
        import io
        self.client.force_authenticate(user=self.recruiter)

        # Before archive: 1 application visible
        res_manage = self.client.get('/jobs/?manage=true', HTTP_HOST='localhost')
        self.assertEqual(res_manage.status_code, status.HTTP_200_OK)
        jobs = self._get_jobs_list(res_manage)
        job_data = next((j for j in jobs if j['id'] == self.job.id), None)
        self.assertIsNotNone(job_data)
        self.assertEqual(job_data['applications_count'], 1)

        res_apps = self.client.get('/applications/', HTTP_HOST='localhost')
        self.assertEqual(res_apps.status_code, status.HTTP_200_OK)
        apps = self._get_apps_list(res_apps)
        self.assertEqual(len(apps), 1)

        # Archive
        call_command('reset_test_applicants', confirm=True, stdout=io.StringIO())

        # After archive: 0 applications visible on recruiter dashboard
        res_manage_after = self.client.get('/jobs/?manage=true', HTTP_HOST='localhost')
        self.assertEqual(res_manage_after.status_code, status.HTTP_200_OK)
        jobs_after = self._get_jobs_list(res_manage_after)
        job_data_after = next((j for j in jobs_after if j['id'] == self.job.id), None)
        self.assertIsNotNone(job_data_after)
        self.assertEqual(job_data_after['applications_count'], 0)

        res_apps_after = self.client.get('/applications/', HTTP_HOST='localhost')
        self.assertEqual(res_apps_after.status_code, status.HTTP_200_OK)
        apps_after = self._get_apps_list(res_apps_after)
        self.assertEqual(len(apps_after), 0)

    def test_restore_works(self):
        from django.core.management import call_command
        import io
        call_command('reset_test_applicants', confirm=True, stdout=io.StringIO())
        self.application.refresh_from_db()
        batch_id = self.application.archive_batch
        self.assertIsNotNone(self.application.archived_at)

        # Restore by batch
        call_command('restore_archived_applicants', batch=batch_id, stdout=io.StringIO())
        self.application.refresh_from_db()
        self.assertIsNone(self.application.archived_at)
        self.assertEqual(self.application.archive_batch, '')

        # Confirm visible again on recruiter dashboard
        self.client.force_authenticate(user=self.recruiter)
        res_manage = self.client.get('/jobs/?manage=true', HTTP_HOST='localhost')
        jobs = self._get_jobs_list(res_manage)
        job_data = next((j for j in jobs if j['id'] == self.job.id), None)
        self.assertEqual(job_data['applications_count'], 1)

    def test_fresh_application_is_allowed_after_archiving(self):
        from django.core.management import call_command
        import io
        call_command('reset_test_applicants', confirm=True, stdout=io.StringIO())

        # The candidate submits a fresh application for the same job
        fresh_resume = SimpleUploadedFile(
            'new_resume.txt',
            b'Fresh resume content after reset.',
            content_type='text/plain',
        )
        fresh_app = Application.objects.create(
            job=self.job,
            candidate=self.candidate,
            full_name='Test Candidate',
            email='cand_archive@test.com',
            phone_number='1234567890',
            university_name='Tech University',
            academic_level='Master',
            graduation_year=2022,
            major='Computer Science',
            skills='Python, Django, FastAPI',
            resume_snapshot=fresh_resume,
        )

        self.assertIsNotNone(fresh_app.id)
        self.assertIsNone(fresh_app.archived_at)

        # Check recruiter dashboard displays exactly 1 applicant (the fresh one)
        self.client.force_authenticate(user=self.recruiter)
        res_manage = self.client.get('/jobs/?manage=true', HTTP_HOST='localhost')
        jobs = self._get_jobs_list(res_manage)
        job_data = next((j for j in jobs if j['id'] == self.job.id), None)
        self.assertEqual(job_data['applications_count'], 1)

        # Total rows in DB is 2 (1 archived, 1 active)
        self.assertEqual(Application.objects.filter(job=self.job).count(), 2)

