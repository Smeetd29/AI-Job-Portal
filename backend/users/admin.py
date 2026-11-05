from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from .models import User, CandidateProfile, RecruiterProfile

@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    list_display = ('id', 'username', 'email', 'is_candidate', 'is_recruiter', 'is_staff', 'is_superuser')
    list_filter = DjangoUserAdmin.list_filter + ('is_candidate', 'is_recruiter')

@admin.register(CandidateProfile)
class CandidateProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'phone')
    search_fields = ('user__username', 'user__email')

@admin.register(RecruiterProfile)
class RecruiterProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'company_name')
    search_fields = ('user__username', 'company_name')
