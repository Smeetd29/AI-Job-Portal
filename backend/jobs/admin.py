from django.contrib import admin
from .models import Job, SavedJob

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'recruiter', 'job_type', 'is_active', 'created_at')
    list_filter = ('is_active', 'job_type', 'location_type')
    search_fields = ('title', 'recruiter__username', 'category')

@admin.register(SavedJob)
class SavedJobAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'job', 'saved_at')
