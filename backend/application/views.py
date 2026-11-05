from django.db import IntegrityError
from django.utils import timezone
from django.core.cache import cache
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from .ai.pipeline import AIServiceError, analyze_resume
from .models import Application
from .serializers import ApplicationSerializer, ApplicationStatusUpdateSerializer

class IsRecruiter(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_recruiter

class IsCandidate(permissions.BasePermission):
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.is_candidate

class ApplicationViewSet(viewsets.ModelViewSet):
    serializer_class = ApplicationSerializer
    throttle_scope = 'sustained'

    def get_permissions(self):
        if self.action in ['create', 'autofill']:
            return [IsCandidate()]
        if self.action in ['update', 'partial_update']:
            return [IsRecruiter()]
        return [permissions.IsAuthenticated()]

    def get_serializer_class(self):
        if self.action in ['update', 'partial_update'] and self.request.user.is_recruiter:
            return ApplicationStatusUpdateSerializer
        return ApplicationSerializer

    def perform_create(self, serializer):
        resume = self.request.FILES.get('resume_snapshot') or getattr(self.request.user.candidate_profile, 'resume', None)

        if not resume:
            raise ValidationError({
                'resume_snapshot': 'Please upload a resume for this application or add a default resume to your profile.'
            })

        try:
            serializer.save(candidate=self.request.user, resume_snapshot=resume)
        except IntegrityError:
            raise ValidationError({'non_field_errors': ['You have already applied to this job.']})

    def get_queryset(self):
        user = self.request.user
        if user.is_recruiter:
            return Application.objects.filter(job__recruiter=user, archived_at__isnull=True).select_related('job', 'candidate').order_by('-applied_at')
        return Application.objects.filter(candidate=user, archived_at__isnull=True).select_related('job').order_by('-applied_at')

    @action(detail=True, methods=['post'], permission_classes=[IsRecruiter])
    def summarize(self, request, pk=None):
        application = self.get_object()

        if application.job.recruiter_id != request.user.id:
            return Response({'detail': 'Not allowed.'}, status=status.HTTP_403_FORBIDDEN)

        regenerate = bool(request.data.get('regenerate'))
        cache_key = f"match_summary_{application.id}"

        if application.ai_summary and not regenerate:
            cached_summary = cache.get(cache_key) or application.ai_summary
            return Response({
                'ai_summary': cached_summary,
                'ai_summary_generated_at': application.ai_summary_generated_at,
                'cached': True,
            })

        resume_file = application.resume_snapshot
        if not resume_file:
            cand_profile = getattr(application.candidate, 'candidate_profile', None)
            fallback = getattr(cand_profile, 'resume', None)
            if fallback:
                try:
                    application.resume_snapshot = fallback
                    application.save(update_fields=['resume_snapshot'])
                    resume_file = fallback
                except Exception:
                    resume_file = fallback

        try:
            analysis = analyze_resume(
                file_field=resume_file,
                job_title=application.job.title,
                job_description=application.job.description,
                candidate_name=application.full_name,
            )
        except AIServiceError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        application.ai_summary = analysis.model_dump()
        application.ai_summary_generated_at = timezone.now()
        application.save(update_fields=['ai_summary', 'ai_summary_generated_at'])
        cache.set(cache_key, application.ai_summary, timeout=86400 * 7)

        return Response({
            'ai_summary': application.ai_summary,
            'ai_summary_generated_at': application.ai_summary_generated_at,
            'cached': False,
        })

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def resume(self, request, pk=None):
        """Secure, authorized download endpoint for application resume snapshots.

        Enforces object-level access controls:
        - Candidate can only download their own application resume.
        - Recruiter can only download resumes for applications to their own jobs.
        - Unauthorized requests return 404 (or 401 if unauthenticated) without leaking resume existence.
        """
        application = self.get_object()
        resume_file = application.resume_snapshot
        if not resume_file:
            cand_profile = getattr(application.candidate, 'candidate_profile', None)
            fallback = getattr(cand_profile, 'resume', None)
            if fallback:
                try:
                    application.resume_snapshot = fallback
                    application.save(update_fields=['resume_snapshot'])
                    resume_file = fallback
                except Exception:
                    resume_file = fallback

        if not resume_file:
            return Response({'detail': 'No resume snapshot attached to this application.'}, status=status.HTTP_404_NOT_FOUND)

        from django.conf import settings
        from django.http import FileResponse, HttpResponseRedirect
        from pathlib import Path
        import mimetypes

        if getattr(settings, 'USE_S3_STORAGE', False):
            return HttpResponseRedirect(resume_file.url)

        try:
            file_handle = resume_file.open('rb')
            filename = Path(resume_file.name).name
            content_type, _ = mimetypes.guess_type(filename)
            content_type = content_type or 'application/pdf'
            response = FileResponse(file_handle, content_type=content_type)
            response['Content-Disposition'] = f'inline; filename="{filename}"'
            response.xframe_options_exempt = True
            return response
        except Exception:
            return Response({'detail': 'Resume file could not be accessed.'}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=['post'], permission_classes=[IsCandidate])
    def autofill(self, request):
        resume_file = (
            request.FILES.get('resume')
            or request.FILES.get('resume_snapshot')
        )
        if not resume_file and request.data.get('use_profile_resume'):
            cand_prof = getattr(request.user, 'candidate_profile', None)
            resume_file = getattr(cand_prof, 'resume', None)

        if not resume_file:
            return Response(
                {'detail': 'Please provide a resume file or select your saved profile resume.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from application.ai.autofill import ResumeAutofillService
            service = ResumeAutofillService()
            result = service.process(file_source=resume_file, candidate_user=request.user)
            return Response(result.model_dump(), status=status.HTTP_200_OK)
        except Exception as exc:
            return Response({'detail': f'Autofill failed: {str(exc)}'}, status=status.HTTP_502_BAD_GATEWAY)


from rest_framework.views import APIView
import logging
logger = logging.getLogger(__name__)
from .models import InteractionEvent
from .serializers import InteractionEventSerializer

class InteractionEventView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        is_batch = isinstance(request.data, list)
        data = request.data if is_batch else [request.data]

        serializer = InteractionEventSerializer(
            data=data,
            many=True,
            context={"request": request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            instances = serializer.save()
            response_data = InteractionEventSerializer(instances, many=True).data
            if not is_batch:
                return Response(response_data[0], status=status.HTTP_201_CREATED)
            return Response({"created": len(response_data), "events": response_data}, status=status.HTTP_201_CREATED)
        except Exception as exc:
            logger.warning("Failed to persist interaction event: %s", exc)
            return Response({"detail": "Failed to record event."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request, *args, **kwargs):
        user = request.user
        qs = InteractionEvent.objects.all()
        if getattr(user, "is_candidate", False):
            qs = qs.filter(candidate=user)
        elif getattr(user, "is_recruiter", False):
            qs = qs.filter(job__recruiter=user)
        elif not user.is_staff:
            return Response([], status=status.HTTP_200_OK)

        job_id = request.query_params.get("job_id")
        if job_id:
            qs = qs.filter(job_id=job_id)

        event_type = request.query_params.get("event_type")
        if event_type:
            qs = qs.filter(event_type=event_type)

        events = qs[:100]
        data = InteractionEventSerializer(events, many=True).data
        return Response(data, status=status.HTTP_200_OK)
