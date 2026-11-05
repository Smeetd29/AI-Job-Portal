import uuid
from django.conf import settings
from django.db import models


def get_default_max_queue_per_day() -> int:
    return getattr(settings, "DEFAULT_MAX_QUEUE_PER_DAY", 10)


class CandidateProfile(models.Model):
    """Stores candidate profile, experience and plain text resume used as facts."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="candidate_profile",
    )
    full_name = models.CharField(max_length=255)
    headline = models.CharField(max_length=255, blank=True, default="")
    summary = models.TextField(blank=True, default="")
    skills = models.JSONField(default=list, blank=True)
    experience = models.JSONField(default=list, blank=True)
    resume_text = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"{self.full_name} ({self.user.username})"


class JobPreference(models.Model):
    """Candidate job search criteria, guardrails, and agent settings."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.OneToOneField(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="preference",
    )
    target_titles = models.JSONField(default=list, blank=True)
    min_salary = models.PositiveIntegerField(null=True, blank=True)
    salary_currency = models.CharField(max_length=3, default="INR")
    work_modes = models.JSONField(default=list, blank=True)  # ["remote", "hybrid", "onsite"]
    locations = models.JSONField(default=list, blank=True)
    include_keywords = models.JSONField(default=list, blank=True)
    exclude_keywords = models.JSONField(default=list, blank=True)
    exclude_companies = models.JSONField(default=list, blank=True)
    max_queue_per_day = models.PositiveSmallIntegerField(default=get_default_max_queue_per_day)
    min_match_score = models.FloatField(default=0.55)
    agent_enabled = models.BooleanField(default=True)
    last_run_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Preferences for {self.candidate.full_name}"


class Job(models.Model):
    """Normalized jobs fetched from various sources."""
    WORK_MODE_CHOICES = [
        ("remote", "Remote"),
        ("hybrid", "Hybrid"),
        ("onsite", "Onsite"),
        ("unknown", "Unknown"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    source = models.CharField(max_length=50)
    external_id = models.CharField(max_length=255)
    title = models.CharField(max_length=255)
    company = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True, default="")
    work_mode = models.CharField(max_length=20, choices=WORK_MODE_CHOICES, default="unknown")
    salary_min = models.PositiveIntegerField(null=True, blank=True)
    salary_max = models.PositiveIntegerField(null=True, blank=True)
    salary_currency = models.CharField(max_length=3, blank=True, default="")
    description = models.TextField()
    apply_url = models.URLField(max_length=2048)
    posted_at = models.DateTimeField(null=True, blank=True)
    raw = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("source", "external_id")
        indexes = [
            models.Index(fields=["posted_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} @ {self.company} ({self.source})"


class QueueItem(models.Model):
    """The candidate's approval queue for matched jobs."""
    STATUS_CHOICES = [
        ("PENDING", "PENDING"),
        ("APPROVED", "APPROVED"),
        ("APPLIED", "APPLIED"),
        ("REJECTED", "REJECTED"),
        ("EXPIRED", "EXPIRED"),
        ("FAILED", "FAILED"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="queue_items",
    )
    job = models.ForeignKey(
        Job,
        on_delete=models.CASCADE,
        related_name="queue_items",
    )
    match_score = models.FloatField()
    match_reasons = models.JSONField(default=list, blank=True)
    cover_note = models.TextField(blank=True, default="")
    cover_note_model = models.CharField(max_length=100, blank=True, default="")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    decided_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()
    apply_result = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    archived_at = models.DateTimeField(null=True, blank=True, db_index=True)
    archive_batch = models.CharField(max_length=64, blank=True, default="")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "job"],
                name="unique_active_candidate_job_queue_item",
                condition=models.Q(archived_at__isnull=True),
            )
        ]
        indexes = [
            models.Index(fields=["candidate", "status"]),
        ]

    def __str__(self) -> str:
        return f"[{self.status}] {self.candidate.full_name} -> {self.job.title}"


class AgentRun(models.Model):
    """Audit log of each candidate's agent pipeline run."""
    STATUS_CHOICES = [
        ("OK", "OK"),
        ("PARTIAL", "PARTIAL"),
        ("ERROR", "ERROR"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    candidate = models.ForeignKey(
        CandidateProfile,
        on_delete=models.CASCADE,
        related_name="agent_runs",
    )
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    jobs_fetched = models.PositiveIntegerField(default=0)
    jobs_matched = models.PositiveIntegerField(default=0)
    items_queued = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="OK")
    error = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        return f"Run {self.id} for {self.candidate.full_name} [{self.status}]"
