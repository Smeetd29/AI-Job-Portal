from rest_framework import serializers
from .models import CandidateProfile, JobPreference, Job, QueueItem, AgentRun


class JobSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = [
            "id",
            "source",
            "external_id",
            "title",
            "company",
            "location",
            "work_mode",
            "salary_min",
            "salary_max",
            "salary_currency",
            "apply_url",
            "posted_at",
        ]


class JobDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = Job
        fields = "__all__"


class JobPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = JobPreference
        fields = [
            "id",
            "target_titles",
            "min_salary",
            "salary_currency",
            "work_modes",
            "locations",
            "include_keywords",
            "exclude_keywords",
            "exclude_companies",
            "max_queue_per_day",
            "min_match_score",
            "agent_enabled",
            "last_run_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "last_run_at", "created_at", "updated_at"]


class QueueItemSerializer(serializers.ModelSerializer):
    job = JobSummarySerializer(read_only=True)
    apply_url = serializers.CharField(source="job.apply_url", read_only=True)

    class Meta:
        model = QueueItem
        fields = [
            "id",
            "candidate",
            "job",
            "apply_url",
            "match_score",
            "match_reasons",
            "cover_note",
            "cover_note_model",
            "status",
            "decided_at",
            "expires_at",
            "apply_result",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "candidate",
            "job",
            "match_score",
            "match_reasons",
            "cover_note_model",
            "status",
            "decided_at",
            "expires_at",
            "apply_result",
            "created_at",
            "updated_at",
        ]


class QueueItemDetailSerializer(serializers.ModelSerializer):
    job = JobDetailSerializer(read_only=True)
    apply_url = serializers.CharField(source="job.apply_url", read_only=True)

    class Meta:
        model = QueueItem
        fields = "__all__"


class AgentRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = AgentRun
        fields = [
            "id",
            "candidate",
            "started_at",
            "finished_at",
            "jobs_fetched",
            "jobs_matched",
            "items_queued",
            "status",
            "error",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields
