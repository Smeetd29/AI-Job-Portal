import logging
from rest_framework import serializers
from users.serializers import UserSerializer
import datetime
from django.utils import timezone
from .models import Application, ApplicationStatusLog, InteractionEvent

logger = logging.getLogger(__name__)

class ApplicationStatusLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ApplicationStatusLog
        fields = ['old_status', 'new_status', 'changed_at']

class ApplicationSerializer(serializers.ModelSerializer):
    candidate_details = UserSerializer(source='candidate', read_only=True)
    job_title = serializers.ReadOnlyField(source='job.title')
    company_name = serializers.ReadOnlyField(source='job.recruiter.recruiter_profile.company_name')
    status_history = ApplicationStatusLogSerializer(source='status_logs', many=True, read_only=True)
    resume_url = serializers.SerializerMethodField()
    job_details = serializers.SerializerMethodField()

    class Meta:
        model = Application
        fields = [
            'id', 'job', 'job_title', 'company_name', 'job_details', 'candidate', 'candidate_details',
            'full_name', 'email', 'phone_number',
            'university_name', 'university_country', 'academic_level',
            'stream', 'current_year', 'graduation_year', 'major', 'minor',
            'grading_system', 'overall_grade', 'skills', 'area_of_interest',
            'linkedin_profile', 'github_profile', 'referral_source',
            'work_authorization_country', 'resume_snapshot', 'resume_url', 'cover_letter', 
            'status', 'status_history', 'applied_at', 'ai_summary', 'ai_summary_generated_at'
        ]
        read_only_fields = ('candidate', 'applied_at', 'status', 'ai_summary', 'ai_summary_generated_at')

    def get_job_details(self, obj):
        if not obj.job:
            return None
        recruiter_profile = getattr(getattr(obj.job, 'recruiter', None), 'recruiter_profile', None)
        return {
            'id': obj.job.id,
            'title': obj.job.title,
            'company': getattr(recruiter_profile, 'company_name', '') or '',
            'location': getattr(obj.job, 'location', '') or '',
            'job_type': getattr(obj.job, 'job_type', '') or '',
        }

    def validate_resume_snapshot(self, value):
        if value.size > 10 * 1024 * 1024:
            raise serializers.ValidationError("File size too large. Max size is 10MB.")

        allowed_extensions = ['.pdf', '.doc', '.docx']
        file_ext = '.' + value.name.lower().split('.')[-1]
        if file_ext not in allowed_extensions:
            raise serializers.ValidationError("Only PDF, DOC, and DOCX files are allowed.")

        return value

    def get_resume_url(self, obj):
        resume_file = obj.resume_snapshot or getattr(getattr(obj.candidate, 'candidate_profile', None), 'resume', None)
        if not resume_file:
            return None
        return f"/api/applications/{obj.id}/resume/"

class ApplicationStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Application
        fields = ['status']

    def validate_resume_snapshot(self, value):
        from application.validators import validate_resume_upload
        validate_resume_upload(value)
        return value

    def update(self, instance, validated_data):
        old_status = instance.status
        new_status = validated_data.get('status')

        if old_status != new_status:
            ApplicationStatusLog.objects.create(
                application=instance,
                old_status=old_status,
                new_status=new_status
            )
            logger.info("Application %s status updated: %s -> %s", instance.id, old_status, new_status)

        return super().update(instance, validated_data)


class InteractionEventSerializer(serializers.ModelSerializer):
    class Meta:
        model = InteractionEvent
        fields = [
            'id', 'event_id', 'candidate', 'job', 'event_type', 'event_timestamp',
            'session_id', 'recommendation_position', 'model_version', 'experiment_id',
            'event_source', 'consent_status', 'metadata',
        ]
        read_only_fields = ('id', 'event_id', 'event_timestamp')

    def validate(self, attrs):
        user = self.context.get('request').user if self.context.get('request') else None
        event_type = attrs.get('event_type')
        candidate = attrs.get('candidate')
        job = attrs.get('job')

        if not user or not user.is_authenticated:
            raise serializers.ValidationError('Authentication required.')

        # Candidate events (job_view, job_save, application_start, application_submit):
        # Must be recorded by the candidate themselves
        if event_type in InteractionEvent.CANDIDATE_EVENTS:
            if candidate != user:
                raise serializers.ValidationError('Users cannot record candidate interaction events for another user.')

        # Recruiter events (recruiter_shortlist, interview_invite, offer, rejection):
        # Must be recorded by the recruiter who owns the job or staff
        if event_type in InteractionEvent.RECRUITER_EVENTS:
            if not (user.is_staff or getattr(user, 'is_recruiter', False)):
                raise serializers.ValidationError('Only recruiters can record recruiter outcome events.')
            if job.recruiter != user and not user.is_staff:
                raise serializers.ValidationError('Recruiters can only record outcome events for their own jobs.')

        return attrs

    def create(self, validated_data):
        event_type = validated_data.get('event_type')
        candidate = validated_data.get('candidate')
        job = validated_data.get('job')
        session_id = validated_data.get('session_id', '')

        # Deduplication for rapid clicks
        if event_type in (InteractionEvent.EVENT_JOB_VIEW, InteractionEvent.EVENT_JOB_SAVE):
            five_mins_ago = timezone.now() - datetime.timedelta(minutes=5)
            existing = InteractionEvent.objects.filter(
                candidate=candidate,
                job=job,
                event_type=event_type,
                session_id=session_id,
                event_timestamp__gte=five_mins_ago,
            ).first()
            if existing:
                return existing

        return super().create(validated_data)
