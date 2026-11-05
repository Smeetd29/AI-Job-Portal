import uuid
from django.db import models
from django.utils import timezone
from users.models import User
from jobs.models import Job

class Application(models.Model):
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING', 'Pending'),
        ('REVIEWING', 'Reviewing'),
        ('SHORTLISTED', 'Shortlisted'),
        ('REJECTED', 'Rejected'),
        ('ACCEPTED', 'Accepted'),
    ]

    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='applications')
    candidate = models.ForeignKey(User, on_delete=models.CASCADE, related_name='my_applications')
    source = models.CharField(max_length=50, default='web', blank=True)
    
    full_name = models.CharField(max_length=255)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
   
    university_name = models.CharField(max_length=255)
    university_country = models.CharField(max_length=100)
    academic_level = models.CharField(max_length=100) 
    stream = models.CharField(max_length=100) 
    current_year = models.CharField(max_length=50) 
    graduation_year = models.IntegerField()
    major = models.CharField(max_length=255)
    minor = models.CharField(max_length=255, blank=True)
    grading_system = models.CharField(max_length=50) 
    overall_grade = models.CharField(max_length=50)

    skills = models.TextField() 
    area_of_interest = models.CharField(max_length=255)
    linkedin_profile = models.URLField()
    github_profile = models.URLField(blank=True)

    referral_source = models.CharField(max_length=255) 
    work_authorization_country = models.CharField(max_length=100)

    resume_snapshot = models.FileField(upload_to='application_resumes/')
    cover_letter = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PENDING')
    applied_at = models.DateTimeField(auto_now_add=True)

    ai_summary = models.JSONField(null=True, blank=True)
    ai_summary_generated_at = models.DateTimeField(null=True, blank=True)

    archived_at = models.DateTimeField(null=True, blank=True, db_index=True)
    archive_batch = models.CharField(max_length=64, blank=True, default='')

    class Meta:
        ordering = ['-applied_at']
        indexes = [
            models.Index(fields=['job', 'status'], name='app_job_status_idx'),
            models.Index(fields=['candidate', 'status'], name='app_cand_status_idx'),
            models.Index(fields=['status', '-applied_at'], name='app_status_applied_idx'),
            models.Index(fields=['candidate', 'job'], name='app_cand_job_idx'),
            models.Index(fields=['job', 'archived_at'], name='app_job_archived_idx'),
            models.Index(fields=['candidate', 'archived_at'], name='app_cand_archived_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['job', 'candidate'],
                name='unique_active_job_candidate_application',
                condition=models.Q(archived_at__isnull=True),
            )
        ]

    def __str__(self):
        return f"{self.candidate.username} -> {self.job.title}"

class ApplicationStatusLog(models.Model):
    application = models.ForeignKey(Application, on_delete=models.CASCADE, related_name='status_logs')
    old_status = models.CharField(max_length=20)
    new_status = models.CharField(max_length=20)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['application', '-changed_at'], name='app_status_log_idx'),
            models.Index(fields=['new_status', '-changed_at'], name='app_log_status_idx'),
        ]

    def __str__(self):
        return f"{self.application.id}: {self.old_status} -> {self.new_status}"


class InteractionEvent(models.Model):
    EVENT_JOB_VIEW = 'job_view'
    EVENT_JOB_SAVE = 'job_save'
    EVENT_APP_START = 'application_start'
    EVENT_APP_SUBMIT = 'application_submit'
    EVENT_RECRUITER_SHORTLIST = 'recruiter_shortlist'
    EVENT_INTERVIEW_INVITE = 'interview_invite'
    EVENT_OFFER = 'offer'
    EVENT_REJECTION = 'rejection'

    EVENT_TYPE_CHOICES = [
        (EVENT_JOB_VIEW, 'Job View'),
        (EVENT_JOB_SAVE, 'Job Save'),
        (EVENT_APP_START, 'Application Start'),
        (EVENT_APP_SUBMIT, 'Application Submit'),
        (EVENT_RECRUITER_SHORTLIST, 'Recruiter Shortlist'),
        (EVENT_INTERVIEW_INVITE, 'Interview Invite'),
        (EVENT_OFFER, 'Offer'),
        (EVENT_REJECTION, 'Rejection'),
    ]

    CANDIDATE_EVENTS = {
        EVENT_JOB_VIEW,
        EVENT_JOB_SAVE,
        EVENT_APP_START,
        EVENT_APP_SUBMIT,
    }

    RECRUITER_EVENTS = {
        EVENT_RECRUITER_SHORTLIST,
        EVENT_INTERVIEW_INVITE,
        EVENT_OFFER,
        EVENT_REJECTION,
    }

    event_id = models.CharField(max_length=64, unique=True, default=uuid.uuid4, db_index=True)
    candidate = models.ForeignKey(User, on_delete=models.CASCADE, related_name='interaction_events')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='interaction_events')
    event_type = models.CharField(max_length=32, choices=EVENT_TYPE_CHOICES, db_index=True)
    event_timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    session_id = models.CharField(max_length=64, blank=True, default='')
    recommendation_position = models.IntegerField(null=True, blank=True)
    model_version = models.CharField(max_length=64, blank=True, default='')
    experiment_id = models.CharField(max_length=64, blank=True, default='')
    event_source = models.CharField(max_length=64, blank=True, default='web')
    consent_status = models.CharField(max_length=32, blank=True, default='granted')
    metadata = models.JSONField(blank=True, default=dict)

    class Meta:
        ordering = ['-event_timestamp']
        indexes = [
            models.Index(fields=['candidate', 'job', 'event_type'], name='idx_interact_cand_job_evt'),
            models.Index(fields=['event_type', '-event_timestamp'], name='idx_interact_evt_time'),
            models.Index(fields=['session_id'], name='idx_interact_session'),
        ]

    def __str__(self):
        return f'{self.event_type} - Cand:{self.candidate_id} Job:{self.job_id} ({self.event_timestamp})'
