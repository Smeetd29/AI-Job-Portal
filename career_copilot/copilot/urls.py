from django.urls import path
from .views import (
    PreferenceView,
    QueueListView,
    QueueDetailView,
    QueueApproveView,
    QueueRejectView,
    QueueApproveAllView,
    AgentRunNowView,
    AgentRunsListView,
    AgentPauseView,
    AgentResumeView,
)

app_name = "copilot"

urlpatterns = [
    # Preferences
    path("preferences/", PreferenceView.as_view(), name="preferences"),

    # Queue
    path("queue/", QueueListView.as_view(), name="queue-list"),
    path("queue/approve-all/", QueueApproveAllView.as_view(), name="queue-approve-all"),
    path("queue/<uuid:pk>/", QueueDetailView.as_view(), name="queue-detail"),
    path("queue/<uuid:pk>/approve/", QueueApproveView.as_view(), name="queue-approve"),
    path("queue/<uuid:pk>/reject/", QueueRejectView.as_view(), name="queue-reject"),

    # Agent controls
    path("agent/run-now/", AgentRunNowView.as_view(), name="agent-run-now"),
    path("agent/runs/", AgentRunsListView.as_view(), name="agent-runs"),
    path("agent/pause/", AgentPauseView.as_view(), name="agent-pause"),
    path("agent/resume/", AgentResumeView.as_view(), name="agent-resume"),
]
