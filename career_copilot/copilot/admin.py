from django.contrib import admin
from .models import CandidateProfile, JobPreference, Job, QueueItem, AgentRun


@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ("full_name", "user", "headline", "created_at")
    search_fields = ("full_name", "user__username", "user__email", "headline")


@admin.register(JobPreference)
class JobPreferenceAdmin(admin.ModelAdmin):
    list_display = ("candidate", "min_salary", "salary_currency", "agent_enabled", "last_run_at")
    list_filter = ("agent_enabled", "salary_currency")
    search_fields = ("candidate__full_name", "candidate__user__username")


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "source", "work_mode", "location", "posted_at")
    list_filter = ("source", "work_mode")
    search_fields = ("title", "company", "location")


@admin.register(QueueItem)
class QueueItemAdmin(admin.ModelAdmin):
    list_display = ("candidate", "job", "status", "match_score", "expires_at", "decided_at")
    list_filter = ("status",)
    search_fields = ("candidate__full_name", "job__title", "job__company")


@admin.register(AgentRun)
class AgentRunAdmin(admin.ModelAdmin):
    list_display = ("candidate", "status", "jobs_fetched", "jobs_matched", "items_queued", "started_at")
    list_filter = ("status",)
    search_fields = ("candidate__full_name",)
