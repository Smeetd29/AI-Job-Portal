from django.contrib import admin
from .models import Application, ApplicationStatusLog


class ArchivedStatusFilter(admin.SimpleListFilter):
    title = 'Archive Status'
    parameter_name = 'archive_status'

    def lookups(self, request, model_admin):
        return (
            ('active', 'Active (Unarchived)'),
            ('archived', 'Archived'),
        )

    def queryset(self, request, queryset):
        if self.value() == 'active':
            return queryset.filter(archived_at__isnull=True)
        if self.value() == 'archived':
            return queryset.filter(archived_at__isnull=False)
        return queryset


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ('id', 'full_name', 'email', 'job', 'status', 'applied_at', 'archived_at', 'archive_batch')
    list_filter = (ArchivedStatusFilter, 'status', 'applied_at', 'archived_at', 'archive_batch')
    search_fields = ('full_name', 'email', 'candidate__username', 'archive_batch')


@admin.register(ApplicationStatusLog)
class ApplicationStatusLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'application', 'old_status', 'new_status', 'changed_at')
