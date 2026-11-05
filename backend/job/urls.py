from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from rest_framework.routers import DefaultRouter
from users import views
from jobs.views import JobViewSet, SavedJobViewSet
from application.views import ApplicationViewSet, InteractionEventView

router = DefaultRouter()
router.register(r'jobs', JobViewSet, basename='job')
router.register(r'applications', ApplicationViewSet, basename='application')
router.register(r'saved-jobs', SavedJobViewSet, basename='saved-job')

from application.ai.recommendations import JobRecommendationsView
from job.health import healthz, readyz

urlpatterns = [
    path('', include('django_prometheus.urls')),
    path('healthz', healthz, name='healthz'),
    path('readyz', readyz, name='readyz'),
    path('api/healthz', healthz, name='api-healthz'),
    path('api/readyz', readyz, name='api-readyz'),
    path('admin/', admin.site.urls),
    path('api/csrf/', views.csrf_token_view, name='csrf-token'),
    path('api/signup/', views.signup, name='signup'),
    path('api/login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('api/logout/', views.logout_view, name='api-logout'),
    path('profile/', views.profile, name='profile'),
    path('api/profile/', views.profile, name='api-profile'),
    path('profile/resume/', views.profileupdate, name='profileupdate'),
    path('api/profile/resume/', views.profileupdate, name='api-profileupdate'),
    path('api/profile/insights/', views.resume_insights, name='api-profile-insights'),
    path('api/ai/recommendations/', JobRecommendationsView.as_view(), name='ai-recommendations'),
    path('ai/recommendations/', JobRecommendationsView.as_view(), name='ai-recommendations-direct'),
    path('api/interactions/events/', InteractionEventView.as_view(), name='interaction-events'),
    path('api/agents/', include('agents.urls')),
    path('api/', include('agents.urls')),
    path('api/', include(router.urls)),
    path('', include(router.urls)),
]

if settings.DEBUG:
    # Only serve media files directly in development. In production, access is authenticated.
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

    
