from django.urls import path
from agents.views import (
    ScreeningQueueView,
    ScreeningApproveView,
    ScreeningOverrideView,
    ScreeningSettingsView,
    DigestSettingsView,
    DigestSendNowView,
    AutoApplySettingsView,
    AutoApplyPendingView,
    AutoApplyApproveView,
    AutoApplyRejectView,
    AutoApplyEditAndApproveView,
    AutoApplyRunNowView,
    SchedulingProposeView,
    SchedulingSlotDetailView,
    SchedulingConfirmView,
)

urlpatterns = [
    path('screening/queue/', ScreeningQueueView.as_view(), name='screening-queue'),
    path('screening/<int:action_id>/approve/', ScreeningApproveView.as_view(), name='screening-approve'),
    path('screening/<int:action_id>/override/', ScreeningOverrideView.as_view(), name='screening-override'),
    path('screening/settings/', ScreeningSettingsView.as_view(), name='screening-settings'),

    path('digest/settings/', DigestSettingsView.as_view(), name='digest-settings'),
    path('digest/send-now/', DigestSendNowView.as_view(), name='digest-send-now'),

    path('auto-apply/settings/', AutoApplySettingsView.as_view(), name='auto-apply-settings'),
    path('auto-apply/pending/', AutoApplyPendingView.as_view(), name='auto-apply-pending'),
    path('auto-apply/<int:action_id>/approve/', AutoApplyApproveView.as_view(), name='auto-apply-approve'),
    path('auto-apply/<int:action_id>/reject/', AutoApplyRejectView.as_view(), name='auto-apply-reject'),
    path('auto-apply/<int:action_id>/edit-and-approve/', AutoApplyEditAndApproveView.as_view(), name='auto-apply-edit-and-approve'),
    path('auto-apply/run-now/', AutoApplyRunNowView.as_view(), name='auto-apply-run-now'),

    path('scheduling/propose/', SchedulingProposeView.as_view(), name='scheduling-propose'),
    path('schedule/<str:magic_token>/', SchedulingSlotDetailView.as_view(), name='scheduling-slot-detail'),
    path('schedule/<str:magic_token>/confirm/', SchedulingConfirmView.as_view(), name='scheduling-confirm'),
]
