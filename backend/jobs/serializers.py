from rest_framework import serializers
from .models import Job, SavedJob

class JobSerializer(serializers.ModelSerializer):
    recruiter_name = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()
    applications_count = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = '__all__'
        read_only_fields = ('recruiter', 'created_at', 'updated_at')

    def get_recruiter_name(self, obj):
        return getattr(getattr(obj.recruiter, 'recruiter_profile', None), 'company_name', None)

    def get_is_saved(self, obj):
        request = self.context.get('request')
        return bool(request and request.user.is_authenticated and obj.saved_by_users.filter(user=request.user).exists())

    def get_applications_count(self, obj):
        count = getattr(obj, 'applications_count', None)
        if count is not None:
            return count
        return obj.applications.count()

class SavedJobSerializer(serializers.ModelSerializer):
    job_details = JobSerializer(source='job', read_only=True)

    class Meta:
        model = SavedJob
        fields = ['id', 'job', 'job_details', 'saved_at']
        read_only_fields = ['saved_at']