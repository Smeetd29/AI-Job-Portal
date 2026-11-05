from django.db import models
from django.utils import timezone
from rest_framework import filters, permissions, status, viewsets
from rest_framework.response import Response

from .models import Job, SavedJob
from .serializers import JobSerializer, SavedJobSerializer

class IsRecruiter(permissions.BasePermission):

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_recruiter)

class IsCandidate(permissions.BasePermission):

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_candidate)

class IsJobOwner(permissions.BasePermission):

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_recruiter)

    def has_object_permission(self, request, view, obj):
        return bool(request.user and request.user.is_authenticated and obj.recruiter == request.user)

class JobViewSet(viewsets.ModelViewSet):
    queryset = Job.objects.all()
    serializer_class = JobSerializer
    throttle_scope = 'burst'
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['title', 'description', 'category']
    ordering_fields = ['created_at', 'pay_amount']

    def get_permissions(self):
        if self.action == 'create':
            return [IsRecruiter()]
        if self.action in ['update', 'partial_update', 'destroy']:
            return [IsRecruiter(), IsJobOwner()]
        return [permissions.AllowAny()]

    def perform_create(self, serializer):
        serializer.save(recruiter=self.request.user)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(
            {'message': 'Job deleted successfully'},
            status=status.HTTP_200_OK
        )

    def get_queryset(self):
        now = timezone.now()
        manage = self.request.query_params.get('manage')

        base_qs = Job.objects.annotate(
            applications_count=models.Count(
                'applications',
                filter=models.Q(applications__archived_at__isnull=True),
            )
        )

        if manage and self.request.user.is_authenticated and self.request.user.is_recruiter:
            return base_qs.filter(recruiter=self.request.user).order_by('-created_at')

        queryset = base_qs.filter(is_active=True)
        queryset = queryset.filter(models.Q(expires_at__gt=now) | models.Q(expires_at__isnull=True))

        category = self.request.query_params.get('category')
        job_type = self.request.query_params.get('job_type')
        location_type = self.request.query_params.get('location_type')
        min_pay = self.request.query_params.get('min_pay')

        if category:
            queryset = queryset.filter(category__iexact=category)
        if job_type:
            queryset = queryset.filter(job_type=job_type)
        if location_type:
            queryset = queryset.filter(location_type=location_type)
        if min_pay:
            queryset = queryset.filter(pay_amount__gte=min_pay)

        return queryset.order_by('-created_at')

class SavedJobViewSet(viewsets.ModelViewSet):
    serializer_class = SavedJobSerializer
    permission_classes = [IsCandidate]

    def get_queryset(self):
        return SavedJob.objects.filter(user=self.request.user).select_related('job')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
