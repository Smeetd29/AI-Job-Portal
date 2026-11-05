from __future__ import annotations

from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from agents.models import AgentAction, AutoApplySettings
from agents.graph import execute_auto_apply_agent
from agents.models import DigestSubscription
from agents.graph import execute_digest_agent
from rest_framework.permissions import AllowAny, IsAuthenticated
from agents.models import InterviewSlotProposal
from agents.graph import execute_scheduling_agent
from agents.tools import book_interview
from agents.models import AgentAction, ScreeningAgentSettings

from application.models import Application

class AutoApplySettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        settings, _ = AutoApplySettings.objects.get_or_create(user=request.user)
        return Response({
            "enabled": settings.enabled,
            "min_score_threshold": settings.min_score_threshold,
            "mode": settings.mode,
            "daily_cap": settings.daily_cap,
            "excluded_companies": settings.excluded_companies,
        })

    def put(self, request):
        settings, _ = AutoApplySettings.objects.get_or_create(user=request.user)
        data = request.data
        if "enabled" in data:
            settings.enabled = bool(data["enabled"])
        if "min_score_threshold" in data:
            settings.min_score_threshold = int(data["min_score_threshold"])
        if "mode" in data and data["mode"] in ("review_first", "auto_submit"):
            settings.mode = data["mode"]
        if "daily_cap" in data:
            settings.daily_cap = int(data["daily_cap"])
        if "excluded_companies" in data and isinstance(data["excluded_companies"], list):
            settings.excluded_companies = data["excluded_companies"]
        settings.save()
        return Response({
            "enabled": settings.enabled,
            "min_score_threshold": settings.min_score_threshold,
            "mode": settings.mode,
            "daily_cap": settings.daily_cap,
            "excluded_companies": settings.excluded_companies,
        })

class AutoApplyPendingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        actions = (
            AgentAction.objects.filter(
                user=request.user,
                agent_type="auto_apply",
                status="pending",
            )
            .select_related("job")
            .order_by("-created_at")
        )
        data = []
        for a in actions:
            data.append({
                "action_id": a.id,
                "application_id": a.object_id,
                "job_id": a.job_id,
                "job_title": a.job.title if a.job else "",
                "company_name": a.job.company_name if a.job else "",
                "score": a.payload.get("score"),
                "cover_letter": a.payload.get("cover_letter"),
                "created_at": a.created_at,
            })
        return Response(data)

class AutoApplyApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, action_id: int):
        action = AgentAction.objects.filter(
            id=action_id,
            user=request.user,
            agent_type="auto_apply",
        ).first()
        if not action:
            return Response({"error": "Action not found"}, status=status.HTTP_404_NOT_FOUND)
        if action.status != "pending":
            return Response({"error": f"Action is already {action.status}"}, status=status.HTTP_400_BAD_REQUEST)
        app = Application.objects.filter(id=action.object_id, candidate=request.user).first()
        if app:
            app.status = "PENDING"
            app.save(update_fields=["status"])
        action.status = "approved"
        action.approved_by = request.user
        action.approved_at = timezone.now()
        action.executed = True
        action.save()
        return Response({"message": "Application submitted successfully"})

class AutoApplyRejectView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, action_id: int):
        action = AgentAction.objects.filter(
            id=action_id,
            user=request.user,
            agent_type="auto_apply",
        ).first()
        if not action:
            return Response({"error": "Action not found"}, status=status.HTTP_404_NOT_FOUND)
        Application.objects.filter(id=action.object_id, candidate=request.user, status="DRAFT").delete()
        action.status = "rejected"
        action.approved_by = request.user
        action.approved_at = timezone.now()
        action.save()
        return Response({"message": "Draft application discarded"})

class AutoApplyEditAndApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, action_id: int):
        action = AgentAction.objects.filter(
            id=action_id,
            user=request.user,
            agent_type="auto_apply",
        ).first()
        if not action:
            return Response({"error": "Action not found"}, status=status.HTTP_404_NOT_FOUND)
        cover_letter = request.data.get("cover_letter")
        if not cover_letter:
            return Response({"error": "Cover letter content required"}, status=status.HTTP_400_BAD_REQUEST)
        app = Application.objects.filter(id=action.object_id, candidate=request.user).first()
        if app:
            app.cover_letter = cover_letter
            app.status = "PENDING"
            app.save(update_fields=["cover_letter", "status"])
        payload = action.payload or {}
        payload["cover_letter"] = cover_letter
        action.payload = payload
        action.status = "approved"
        action.approved_by = request.user
        action.approved_at = timezone.now()
        action.executed = True
        action.save()
        return Response({"message": "Edited application submitted successfully"})

class AutoApplyRunNowView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        result = execute_auto_apply_agent(user_id=request.user.id, trigger="manual")
        if "error" in result:
            return Response({"error": result["error"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        if "skipped" in result:
            return Response({"message": result["skipped"]}, status=status.HTTP_200_OK)
        action_ids = result.get("action_ids", [])
        return Response({
            "message": f"Auto-apply scan executed. {len(action_ids)} applications processed.",
            "action_count": len(action_ids),
        })

class DigestSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        sub, _ = DigestSubscription.objects.get_or_create(user=request.user)
        return Response({
            "frequency": sub.frequency,
            "min_score_threshold": sub.min_score_threshold,
            "max_jobs_per_digest": sub.max_jobs_per_digest,
            "last_sent_at": sub.last_sent_at,
        })

    def put(self, request):
        sub, _ = DigestSubscription.objects.get_or_create(user=request.user)
        data = request.data
        if "frequency" in data and data["frequency"] in ("daily", "weekly", "off"):
            sub.frequency = data["frequency"]
        if "min_score_threshold" in data:
            sub.min_score_threshold = int(data["min_score_threshold"])
        if "max_jobs_per_digest" in data:
            sub.max_jobs_per_digest = int(data["max_jobs_per_digest"])
        sub.save()
        return Response({
            "frequency": sub.frequency,
            "min_score_threshold": sub.min_score_threshold,
            "max_jobs_per_digest": sub.max_jobs_per_digest,
            "last_sent_at": sub.last_sent_at,
        })

class DigestSendNowView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        result = execute_digest_agent(user_id=request.user.id, trigger="manual")
        if "error" in result:
            return Response({"error": result["error"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        if "skipped" in result:
            return Response({"message": result["skipped"]}, status=status.HTTP_200_OK)
        rec_jobs = result.get("recommended_jobs", [])
        return Response({
            "message": f"Digest generated and sent with {len(rec_jobs)} job matches.",
            "recommended_count": len(rec_jobs),
        })

class SchedulingProposeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        application_id = request.data.get("application_id")
        if not application_id:
            return Response({"error": "application_id is required"}, status=status.HTTP_400_BAD_REQUEST)
        app = Application.objects.filter(id=application_id, job__recruiter=request.user).first()
        if not app:
            return Response({"error": "Application not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)
        result = execute_scheduling_agent(application_id=app.id, trigger="manual")
        if "error" in result:
            return Response({"error": result["error"]}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({
            "message": "Interview slots proposed and invitation email sent to candidate",
            "proposal_id": result.get("proposal_id"),
        })

class SchedulingSlotDetailView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, magic_token: str):
        proposal = (
            InterviewSlotProposal.objects.filter(magic_token=magic_token)
            .select_related("application__job", "application__candidate")
            .first()
        )
        if not proposal:
            return Response({"error": "Invalid or expired interview link"}, status=status.HTTP_404_NOT_FOUND)
        app = proposal.application
        return Response({
            "proposal_id": proposal.id,
            "status": proposal.status,
            "candidate_name": app.full_name,
            "job_title": app.job.title,
            "company_name": app.job.company_name,
            "proposed_slots": proposal.proposed_slots,
            "created_at": proposal.created_at,
        })

class SchedulingConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, magic_token: str):
        proposal = (
            InterviewSlotProposal.objects.filter(magic_token=magic_token)
            .select_related("application__job", "application__candidate")
            .first()
        )
        if not proposal:
            return Response({"error": "Invalid or expired interview link"}, status=status.HTTP_404_NOT_FOUND)
        chosen_slot = request.data.get("chosen_slot")
        if not chosen_slot:
            return Response({"error": "chosen_slot (ISO datetime string) is required"}, status=status.HTTP_400_BAD_REQUEST)
        try:
            interview = book_interview(proposal, chosen_slot)
            return Response({
                "message": "Interview booked successfully",
                "scheduled_at": interview.scheduled_at,
                "meeting_link": interview.meeting_link,
            })
        except ValueError as ve:
            return Response({"error": str(ve)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            return Response({"error": f"Booking failed: {str(e)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ScreeningQueueView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        actions = (
            AgentAction.objects.filter(
                agent_type="screening",
                status="pending",
                job__recruiter=request.user,
            )
            .select_related("user", "job")
            .order_by("-created_at")
        )
        data = []
        for a in actions:
            data.append({
                "action_id": a.id,
                "application_id": a.object_id,
                "candidate_name": a.user.get_full_name() or a.user.username if a.user else "Unknown",
                "candidate_email": a.user.email if a.user else "",
                "job_id": a.job_id,
                "job_title": a.job.title if a.job else "",
                "score": a.payload.get("score"),
                "proposed_decision": a.payload.get("decision"),
                "rationale": a.payload.get("rationale"),
                "created_at": a.created_at,
            })
        return Response(data)

class ScreeningApproveView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, action_id: int):
        action = AgentAction.objects.filter(
            id=action_id,
            agent_type="screening",
            job__recruiter=request.user,
        ).first()
        if not action:
            return Response({"error": "Action not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)
        if action.status != "pending":
            return Response({"error": f"Action is already {action.status}"}, status=status.HTTP_400_BAD_REQUEST)
        proposed_decision = action.payload.get("decision")
        application = Application.objects.filter(id=action.object_id).first()
        if application:
            if proposed_decision == "shortlist":
                application.status = "SHORTLISTED"
            elif proposed_decision == "reject":
                application.status = "REJECTED"
            application.save(update_fields=["status"])
        action.status = "approved"
        action.approved_by = request.user
        action.approved_at = timezone.now()
        action.executed = True
        action.save()
        return Response({"message": f"Screening decision '{proposed_decision}' approved successfully"})

class ScreeningOverrideView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, action_id: int):
        action = AgentAction.objects.filter(
            id=action_id,
            agent_type="screening",
            job__recruiter=request.user,
        ).first()
        if not action:
            return Response({"error": "Action not found or unauthorized"}, status=status.HTTP_404_NOT_FOUND)
        override_decision = request.data.get("decision")
        if override_decision not in ("shortlist", "reject"):
            return Response({"error": "Decision must be 'shortlist' or 'reject'"}, status=status.HTTP_400_BAD_REQUEST)
        application = Application.objects.filter(id=action.object_id).first()
        if application:
            application.status = "SHORTLISTED" if override_decision == "shortlist" else "REJECTED"
            application.save(update_fields=["status"])
        payload = action.payload or {}
        payload["override_decision"] = override_decision
        action.payload = payload
        action.status = "approved"
        action.approved_by = request.user
        action.approved_at = timezone.now()
        action.executed = True
        action.save()
        return Response({"message": f"Screening decision overridden to '{override_decision}'"})

class ScreeningSettingsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        settings, _ = ScreeningAgentSettings.objects.get_or_create(recruiter=request.user)
        return Response({
            "enabled": settings.enabled,
            "shortlist_threshold": settings.shortlist_threshold,
            "reject_threshold": settings.reject_threshold,
            "auto_execute_extreme_scores": settings.auto_execute_extreme_scores,
        })

    def put(self, request):
        settings, _ = ScreeningAgentSettings.objects.get_or_create(recruiter=request.user)
        data = request.data
        if "enabled" in data:
            settings.enabled = bool(data["enabled"])
        if "shortlist_threshold" in data:
            settings.shortlist_threshold = int(data["shortlist_threshold"])
        if "reject_threshold" in data:
            settings.reject_threshold = int(data["reject_threshold"])
        if "auto_execute_extreme_scores" in data:
            settings.auto_execute_extreme_scores = bool(data["auto_execute_extreme_scores"])
        settings.save()
        return Response({
            "enabled": settings.enabled,
            "shortlist_threshold": settings.shortlist_threshold,
            "reject_threshold": settings.reject_threshold,
            "auto_execute_extreme_scores": settings.auto_execute_extreme_scores,
        })
