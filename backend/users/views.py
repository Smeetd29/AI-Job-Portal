from django.conf import settings
from django.core.cache import cache
from django.contrib.auth import authenticate, login, logout as auth_logout
from django.middleware.csrf import get_token
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework import permissions
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
import hashlib
import logging

from application.ai.intelligence import PROMPT_VERSION, build_resume_insights
from application.ai.pipeline import AIServiceError, extract_raw_text
from jobs.models import Job
from .serializers import CandidateProfileSerializer, RecruiterProfileSerializer, SignupSerializer, UserSerializer

logger = logging.getLogger(__name__)

class AuthRateThrottle(AnonRateThrottle):
    scope = 'auth_attempt'


class ResumeInsightsRateThrottle(UserRateThrottle):
    scope = 'resume_insights'

@api_view(['GET'])
@permission_classes([permissions.AllowAny])
@ensure_csrf_cookie
def csrf_token_view(request):
    return Response({"csrfToken": get_token(request), "detail": "CSRF cookie set."})

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@throttle_classes([AuthRateThrottle])
@ensure_csrf_cookie
def signup(request):
    serializer = SignupSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        return Response(UserSerializer(user).data, status=201)
    return Response(serializer.errors, status=400)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@throttle_classes([AuthRateThrottle])
@ensure_csrf_cookie
def login_view(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(username=username, password=password)
    if user and settings.PILOT_INVITE_ONLY:
        if (user.email or '').strip().casefold() not in settings.PILOT_INVITED_EMAILS:
            user = None
    if user:
        login(request, user)
        return Response(UserSerializer(user).data)
    return Response({"error": "Invalid Credentials"}, status=401)

@api_view(['POST', 'GET'])
@permission_classes([permissions.AllowAny])
def logout_view(request):
    auth_logout(request)
    if hasattr(request, 'session'):
        request.session.flush()
    response = Response({"message": "Logged out successfully"})
    response.delete_cookie('sessionid')
    response.delete_cookie('csrftoken')
    return response

@api_view(['GET', 'PUT', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
@ensure_csrf_cookie
def profile(request):
    user = request.user
    if request.method == 'GET':
        return Response(UserSerializer(user).data)

    serializer = UserSerializer(user, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data)

    return Response(serializer.errors, status=400)

@api_view(['POST', 'PUT', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
def profileupdate(request):
    if request.user.is_candidate:
        profile = request.user.candidate_profile
        serializer = CandidateProfileSerializer(profile, data=request.data, partial=True)
    else:
        profile = request.user.recruiter_profile
        serializer = RecruiterProfileSerializer(profile, data=request.data, partial=True)

    if serializer.is_valid():
        profile = serializer.save()
        if request.user.is_candidate and 'resume' in request.FILES:
            profile.resume_facts = {}
            profile.save(update_fields=['resume_facts'])
        return Response(serializer.data)

    return Response(serializer.errors, status=400)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@throttle_classes([ResumeInsightsRateThrottle])
def resume_insights(request):
    if not request.user.is_candidate:
        return Response({'detail': 'Resume insights are available to candidates only.'}, status=403)

    profile = getattr(request.user, 'candidate_profile', None)
    if not profile or not profile.resume:
        return Response({'detail': 'Upload a resume to your candidate profile first.'}, status=400)

    job = None
    job_id = request.data.get('job_id')
    if job_id is not None:
        try:
            job = Job.objects.get(pk=job_id, is_active=True)
        except (Job.DoesNotExist, ValueError, TypeError):
            return Response({'detail': 'The selected job is unavailable.'}, status=400)

    file_handle = None
    try:
        if profile.resume.size > 10 * 1024 * 1024:
            return Response({'detail': 'Resume file must be 10 MB or smaller.'}, status=413)
        file_handle = profile.resume.open('rb')
        resume_bytes = file_handle.read()
        profile.resume.seek(0)
        resume_text = extract_raw_text(profile.resume)
    except (OSError, ValueError, AIServiceError) as exc:
        logger.warning("Unable to extract candidate resume text (%s).", type(exc).__name__)
        return Response({'detail': 'Unable to read the uploaded resume.'}, status=422)
    finally:
        if file_handle is not None:
            file_handle.close()

    resume_hash = hashlib.sha256(resume_bytes).hexdigest()
    job_version = f'{job.pk}:{job.updated_at.isoformat()}' if job else 'general'
    cache_key = (
        f'resume_insights:{request.user.pk}:{resume_hash}:{job_version}:'
        f'{settings.ANTHROPIC_MODEL}:{PROMPT_VERSION}'
    )
    insights = cache.get(cache_key)
    cached = insights is not None
    if not cached:
        insights = build_resume_insights(
            resume_text,
            job_title=job.title if job else '',
            job_description=job.description if job else '',
        )
        if job is None:
            profile.resume_facts = {
                'resume_sha256': resume_hash,
                'prompt_version': PROMPT_VERSION,
                'model': insights['model'],
                'facts': insights['verified_facts'],
            }
            profile.save(update_fields=['resume_facts'])
        cache.set(cache_key, insights, timeout=86400)

    return Response({'insights': insights, 'cached': cached})
