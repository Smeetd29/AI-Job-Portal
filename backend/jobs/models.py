from django.db import models
from users.models import User

class Job(models.Model):
    PAY_MODE_CHOICES = [
        ('Monthly', 'Monthly'),
        ('Weekly', 'Weekly'),
        ('Hourly', 'Hourly'),
        ('One-time', 'One-time'),
    ]
    
    JOB_TYPE_CHOICES = [
        ('Full Time', 'Full Time'),
        ('Part Time', 'Part Time'),
        ('Contract', 'Contract'),
        ('Freelance', 'Freelance'),
    ]

    LOCATION_TYPE_CHOICES = [
        ('Remote', 'Remote'),
        ('Hybrid', 'Hybrid'),
        ('Onsite', 'Onsite'),
    ]

    recruiter = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posted_jobs')
    title = models.CharField(max_length=255)
    pay_amount = models.DecimalField(max_digits=12, decimal_places=2)
    pay_mode = models.CharField(max_length=20, choices=PAY_MODE_CHOICES, default='Monthly')
    job_type = models.CharField(max_length=20, choices=JOB_TYPE_CHOICES, default='Full Time')
    location_type = models.CharField(max_length=20, choices=LOCATION_TYPE_CHOICES, default='Onsite')
    category = models.CharField(max_length=100) # e.g., Sales, Engineering
    description = models.TextField()
    
    is_active = models.BooleanField(default=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active', 'expires_at'], name='job_active_expires_idx'),
            models.Index(fields=['is_active', '-created_at'], name='job_active_created_idx'),
            models.Index(fields=['category', 'is_active'], name='job_category_active_idx'),
            models.Index(fields=['recruiter', '-created_at'], name='job_recruiter_created_idx'),
            models.Index(fields=['location_type', 'is_active'], name='job_location_active_idx'),
            models.Index(fields=['job_type', 'is_active'], name='job_type_active_idx'),
        ]

    def __str__(self):
        return self.title

    @property
    def company_name(self):
        profile = getattr(self.recruiter, 'recruiter_profile', None)
        return (getattr(profile, 'company_name', None) or "").strip() or "CareerConnect Partner"

class SavedJob(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='saved_jobs')
    job = models.ForeignKey(Job, on_delete=models.CASCADE, related_name='saved_by_users')
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'job')
        ordering = ['-saved_at']

    def __str__(self):
        return f"{self.user.username} saved {self.job.title}"
