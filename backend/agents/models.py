from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from users.models import User
from jobs.models import Job

class AgentRun(models.Model):
    AGENT_TYPE_CHOICES = [
        ('screening', 'Screening Agent'),
        ('digest', 'Job-Search Digest Agent'),
        ('auto_apply', 'Auto-Apply Agent'),
        ('scheduling', 'Scheduling Agent'),
    ]

    TRIGGER_CHOICES = [
        ('scheduled', 'Scheduled (Beat)'),
        ('event', 'Event-Driven (Signal)'),
        ('manual', 'Manual Trigger'),
    ]

    STATUS_CHOICES = [
        ('running', 'Running'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    agent_type = models.CharField(max_length=50, choices=AGENT_TYPE_CHOICES)
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True, related_name='agent_runs'
    )
    trigger = models.CharField(max_length=30, choices=TRIGGER_CHOICES, default='scheduled')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='running')
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

    class Meta:
        ordering = ['-started_at']
        indexes = [
            models.Index(fields=['status', '-started_at'], name='agent_run_status_idx'),
            models.Index(fields=['agent_type', 'status'], name='agent_run_type_status_idx'),
            models.Index(fields=['user', '-started_at'], name='agent_run_user_idx'),
        ]

    def __str__(self):
        return f"{self.get_agent_type_display()} [{self.status}] at {self.started_at}"

class AgentAction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Approval'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
        ('auto_executed', 'Auto Executed'),
        ('expired', 'Expired'),
    ]

    run = models.ForeignKey(AgentRun, on_delete=models.CASCADE, related_name='actions')
    agent_type = models.CharField(max_length=50, db_index=True)

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    target_object = GenericForeignKey('content_type', 'object_id')

    user = models.ForeignKey(
        User, on_delete=models.CASCADE, null=True, blank=True, related_name='agent_actions'
    )
    job = models.ForeignKey(Job, on_delete=models.CASCADE, null=True, blank=True)

    action_type = models.CharField(max_length=100)
    payload = models.JSONField(default=dict)
    requires_approval = models.BooleanField(default=False)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_agent_actions'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    executed = models.BooleanField(default=False)
    email_state = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        choices=[('sending', 'Sending'), ('sent', 'Sent'), ('failed', 'Failed')],
        default=None,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', '-created_at'], name='act_status_created_idx'),
            models.Index(fields=['user', 'status'], name='act_user_status_idx'),
            models.Index(fields=['agent_type', 'status'], name='act_type_status_idx'),
            models.Index(fields=['job', 'user'], name='act_job_user_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['job', 'user', 'agent_type'],
                name='unique_agent_action_job_user_type',
                condition=models.Q(job__isnull=False, user__isnull=False),
            )
        ]

    def __str__(self):
        return f"{self.agent_type} action ({self.action_type}): {self.status}"

class ScreeningAgentSettings(models.Model):
    recruiter = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='screening_settings'
    )
    enabled = models.BooleanField(default=True)
    shortlist_threshold = models.IntegerField(default=84)
    reject_threshold = models.IntegerField(default=45)
    auto_execute_extreme_scores = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Screening settings for {self.recruiter.username} (enabled={self.enabled})"

class DigestSubscription(models.Model):
    FREQUENCY_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('off', 'Off'),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='digest_subscription'
    )
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='weekly')
    min_score_threshold = models.IntegerField(default=70)
    max_jobs_per_digest = models.IntegerField(default=5)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Digest subscription for {self.user.username} ({self.frequency})"

class AutoApplySettings(models.Model):
    MODE_CHOICES = [
        ('review_first', 'Review First'),
        ('auto_submit', 'Auto Submit'),
    ]

    user = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='auto_apply_settings'
    )
    enabled = models.BooleanField(default=False)
    min_score_threshold = models.IntegerField(default=85)
    mode = models.CharField(max_length=30, choices=MODE_CHOICES, default='review_first')
    daily_cap = models.IntegerField(default=3)
    excluded_companies = models.JSONField(default=list, blank=True)
    settings_changed_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Auto-Apply for {self.user.username} ({self.mode}, enabled={self.enabled})"

class RecruiterCalendarConnection(models.Model):
    PROVIDER_CHOICES = [
        ('google', 'Google Calendar'),
        ('outlook', 'Outlook Calendar'),
    ]

    recruiter = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='calendar_connection'
    )
    provider = models.CharField(max_length=30, choices=PROVIDER_CHOICES, default='google')
    access_token = models.TextField(blank=True)
    refresh_token = models.TextField(blank=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    connected_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.recruiter.username} ({self.provider})"

class InterviewSlotProposal(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending Candidate Confirmation'),
        ('confirmed', 'Confirmed'),
        ('expired', 'Expired'),
    ]

    application = models.ForeignKey(
        'application.Application', on_delete=models.CASCADE, related_name='slot_proposals'
    )
    proposed_slots = models.JSONField(default=list)
    magic_token = models.CharField(max_length=64, unique=True, db_index=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Proposal {self.magic_token[:8]} ({self.status})"

class Interview(models.Model):
    application = models.ForeignKey(
        'application.Application', on_delete=models.CASCADE, related_name='interviews'
    )
    scheduled_at = models.DateTimeField()
    meeting_link = models.URLField(blank=True)
    calendar_event_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Interview for {self.application.full_name} at {self.scheduled_at}"
