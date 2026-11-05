import logging
from datetime import timedelta
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import CandidateProfile, JobPreference, QueueItem, AgentRun
from .serializers import (
    JobPreferenceSerializer,
    QueueItemSerializer,
    QueueItemDetailSerializer,
    AgentRunSerializer,
)
from .services import approval
from .services.approval import InvalidTransition
from .tasks import run_candidate_pipeline

logger = logging.getLogger(__name__)


def _get_candidate_profile(user) -> CandidateProfile:
    """Helper to retrieve or lazily create candidate profile for current authenticated user."""
    profile, _ = CandidateProfile.objects.get_or_create(
        user=user,
        defaults={
            "full_name": user.get_full_name() or user.username,
        },
    )
    return profile


class PreferenceView(APIView):
    """
    GET /api/preferences/ - Read candidate job preferences.
    PUT /api/preferences/ - Update candidate job preferences.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_candidate_profile(request.user)
        pref, _ = JobPreference.objects.get_or_create(candidate=profile)
        serializer = JobPreferenceSerializer(pref)
        return Response(serializer.data)

    def put(self, request):
        profile = _get_candidate_profile(request.user)
        pref, _ = JobPreference.objects.get_or_create(candidate=profile)
        serializer = JobPreferenceSerializer(pref, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class QueueListView(APIView):
    """
    GET /api/queue/?status=PENDING - List queue items scoped to current candidate.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_candidate_profile(request.user)
        queryset = QueueItem.objects.filter(candidate=profile).select_related("job")

        status_filter = request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter.upper())

        queryset = queryset.order_by("-match_score", "-created_at")
        serializer = QueueItemSerializer(queryset, many=True)
        return Response(serializer.data)


class QueueDetailView(APIView):
    """
    GET /api/queue/{id}/ - Retrieve detailed information for a queue item.
    Returns 404 for other candidates' items.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        profile = _get_candidate_profile(request.user)
        item = get_object_or_404(QueueItem.objects.select_related("job"), id=pk, candidate=profile)
        serializer = QueueItemDetailSerializer(item)
        return Response(serializer.data)


class QueueApproveView(APIView):
    """
    POST /api/queue/{id}/approve/
    Body optional: {"cover_note": "edited text"}
    Transitions item from PENDING -> APPROVED -> APPLIED.
    Returns 409 Conflict if already decided.
    Returns 404 if not found or belongs to another user.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        profile = _get_candidate_profile(request.user)
        item = get_object_or_404(QueueItem.objects.select_related("job"), id=pk, candidate=profile)

        edited_note = request.data.get("cover_note") if isinstance(request.data, dict) else None

        try:
            updated_item = approval.approve(item, edited_note=edited_note)
        except InvalidTransition as exc:
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)

        serializer = QueueItemSerializer(updated_item)
        data = serializer.data
        data["apply_url"] = updated_item.job.apply_url
        data["cover_note"] = updated_item.cover_note
        return Response(data, status=status.HTTP_200_OK)


class QueueRejectView(APIView):
    """
    POST /api/queue/{id}/reject/
    Transitions item from PENDING -> REJECTED.
    Returns 409 Conflict if not PENDING.
    Returns 404 if not found or belongs to another candidate.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        profile = _get_candidate_profile(request.user)
        item = get_object_or_404(QueueItem, id=pk, candidate=profile)

        try:
            rejected_item = approval.reject(item)
        except InvalidTransition as exc:
            return Response({"error": str(exc)}, status=status.HTTP_409_CONFLICT)

        serializer = QueueItemSerializer(rejected_item)
        return Response(serializer.data, status=status.HTTP_200_OK)


class QueueApproveAllView(APIView):
    """
    POST /api/queue/approve-all/
    Body: {"ids": ["uuid1", "uuid2"]}
    Batch approves multiple pending items.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = _get_candidate_profile(request.user)
        raw_ids = request.data.get("ids", [])
        if not isinstance(raw_ids, list):
            return Response({"error": "Expected a list of 'ids'"}, status=status.HTTP_400_BAD_REQUEST)

        approved = []
        conflicts = []

        for item_id in raw_ids:
            try:
                item = QueueItem.objects.select_related("job").get(id=item_id, candidate=profile)
                updated = approval.approve(item)
                approved.append(str(updated.id))
            except QueueItem.DoesNotExist:
                continue
            except InvalidTransition:
                conflicts.append(str(item_id))

        return Response(
            {
                "approved_count": len(approved),
                "approved_ids": approved,
                "conflicted_ids": conflicts,
            },
            status=status.HTTP_200_OK,
        )


class AgentRunNowView(APIView):
    """
    POST /api/agent/run-now/
    Manual run: ignores last_run_at and uses a 7-day window so repeated clicks don't return empty.
    Dispatches run_candidate_pipeline.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = _get_candidate_profile(request.user)
        pref, _ = JobPreference.objects.get_or_create(candidate=profile)

        # Ignore last_run_at for manual run and use a 7-day window
        pref.last_run_at = timezone.now() - timedelta(days=7)
        pref.save(update_fields=["last_run_at"])

        try:
            run_candidate_pipeline.delay(str(profile.id))
        except Exception:
            from .services.pipeline import run_for_candidate
            run_for_candidate(str(profile.id))

        return Response(
            {"message": "Career co-pilot run initiated.", "candidate_id": str(profile.id)},
            status=status.HTTP_202_ACCEPTED,
        )


class AgentRunsListView(APIView):
    """
    GET /api/agent/runs/ - Returns last 20 AgentRun rows for current candidate.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = _get_candidate_profile(request.user)
        runs = AgentRun.objects.filter(candidate=profile).order_by("-started_at")[:20]
        serializer = AgentRunSerializer(runs, many=True)
        return Response(serializer.data)


class AgentPauseView(APIView):
    """
    POST /api/agent/pause/ - Pause the autonomous co-pilot for candidate.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = _get_candidate_profile(request.user)
        pref, _ = JobPreference.objects.get_or_create(candidate=profile)
        pref.agent_enabled = False
        pref.save(update_fields=["agent_enabled"])
        return Response({"agent_enabled": False, "status": "paused"})


class AgentResumeView(APIView):
    """
    POST /api/agent/resume/ - Resume the autonomous co-pilot for candidate.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = _get_candidate_profile(request.user)
        pref, _ = JobPreference.objects.get_or_create(candidate=profile)
        pref.agent_enabled = True
        pref.save(update_fields=["agent_enabled"])
        return Response({"agent_enabled": True, "status": "resumed"})
