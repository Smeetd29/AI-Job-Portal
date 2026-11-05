from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, TypedDict
from django.utils import timezone
from langgraph.graph import StateGraph, END
from agents.models import AgentAction, AgentRun, ScreeningAgentSettings
from agents.guardrails import (
    is_agent_enabled, check_weekly_ceiling, get_weekly_application_count, HARD_WEEKLY_APPLICATION_CEILING
)
from agents.tools import (
    score_candidate,
    get_eligible_jobs,
    count_applications_today,
    draft_cover_letter,
    create_or_submit_application,
    notify_candidate_batch,
    get_new_jobs_since,
    template_reason,
    write_digest_intro,
    dispatch_digest,
    get_recruiter_calendar_slots,
    rank_slots,
    create_slot_proposal,
    send_slot_picker_email,
    classify_score,
    write_rationale,
    apply_screening_decision,
)
from jobs.models import Job
from users.models import User
from datetime import timedelta

from application.models import Application

logger = logging.getLogger(__name__)

class AutoApplyState(TypedDict, total=False):
    user_id: int
    run_id: int
    remaining_quota: int
    eligible_jobs: List[Job]
    qualified_jobs: List[Dict[str, Any]]
    action_ids: List[int]
    error: Optional[str]

def check_eligibility_caps_node(state: AutoApplyState) -> Dict[str, Any]:
    user = User.objects.get(id=state["user_id"])
    settings = getattr(user, "auto_apply_settings", None)
    if not settings or not settings.enabled:
        return {"remaining_quota": 0, "eligible_jobs": []}
    
    weekly_count = get_weekly_application_count(user.id)
    remaining_weekly = max(0, HARD_WEEKLY_APPLICATION_CEILING - weekly_count)
    if remaining_weekly <= 0:
        logger.warning("User %s hit weekly hard ceiling (%d/%d)", user.username, weekly_count, HARD_WEEKLY_APPLICATION_CEILING)
        return {"remaining_quota": 0, "eligible_jobs": []}
    
    today_count = count_applications_today(user)
    remaining_daily = max(0, settings.daily_cap - today_count)
    effective_quota = min(remaining_daily, remaining_weekly)
    if effective_quota <= 0:
        return {"remaining_quota": 0, "eligible_jobs": []}
    
    jobs = get_eligible_jobs(user, settings)
    return {"remaining_quota": effective_quota, "eligible_jobs": jobs}

def score_filter_node(state: AutoApplyState) -> Dict[str, Any]:
    quota = state.get("remaining_quota", 0)
    eligible_jobs = state.get("eligible_jobs", [])
    if quota <= 0 or not eligible_jobs:
        return {"qualified_jobs": []}
    user = User.objects.get(id=state["user_id"])
    settings = getattr(user, "auto_apply_settings", None)
    min_thresh = settings.min_score_threshold if settings else 85
    scored: List[Dict[str, Any]] = []
    for job in eligible_jobs:
        score_data = score_candidate(user, job)
        score = score_data.get("overall_score", 0)
        if score >= min_thresh:
            scored.append({"job": job, "score": score, "score_data": score_data})
    scored.sort(key=lambda x: x["score"], reverse=True)
    return {"qualified_jobs": scored[:quota]}

def draft_and_apply_node(state: AutoApplyState) -> Dict[str, Any]:
    qualified = state.get("qualified_jobs", [])
    if not qualified:
        return {"action_ids": []}
    user = User.objects.get(id=state["user_id"])
    run = AgentRun.objects.get(id=state["run_id"])
    settings = user.auto_apply_settings
    mode = settings.mode
    submitted_actions: List[AgentAction] = []
    draft_actions: List[AgentAction] = []
    action_ids: List[int] = []
    for item in qualified:
        job = item["job"]
        score = item["score"]
        score_data = item["score_data"]
        cover_letter = draft_cover_letter(user, job, score_data)
        action = create_or_submit_application(
            user=user,
            job=job,
            cover_letter=cover_letter,
            score=score,
            mode=mode,
            run=run,
        )
        action_ids.append(action.id)
        if mode == "auto_submit":
            submitted_actions.append(action)
        else:
            draft_actions.append(action)
    notify_candidate_batch(user, submitted_actions, draft_actions)
    return {"action_ids": action_ids}

def build_auto_apply_graph():
    builder = StateGraph(AutoApplyState)
    builder.add_node("check_caps", check_eligibility_caps_node)
    builder.add_node("score_filter", score_filter_node)
    builder.add_node("draft_and_apply", draft_and_apply_node)
    builder.set_entry_point("check_caps")
    builder.add_edge("check_caps", "score_filter")
    builder.add_edge("score_filter", "draft_and_apply")
    builder.add_edge("draft_and_apply", END)
    return builder.compile()

auto_apply_graph = build_auto_apply_graph()

def execute_auto_apply_agent(user_id: int, trigger: str = "scheduled") -> Dict[str, Any]:
    if not is_agent_enabled("auto_apply"):
        logger.info("Auto-apply agent is disabled by kill switch.")
        return {"error": "Auto-apply agent is disabled."}
    user = User.objects.filter(id=user_id).first()
    if not user:
        return {"error": f"User {user_id} not found."}
    settings = getattr(user, "auto_apply_settings", None)
    if not settings or not settings.enabled:
        return {"skipped": "Auto-apply is disabled in user settings"}
    run = AgentRun.objects.create(
        agent_type="auto_apply",
        user=user,
        trigger=trigger,
        status="running",
    )
    try:
        initial_state: AutoApplyState = {
            "user_id": user_id,
            "run_id": run.id,
        }
        result = auto_apply_graph.invoke(initial_state)
        run.status = "completed"
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "completed_at"])
        try:
            from agents.metrics import track_agent_run
            track_agent_run("auto_apply", trigger, "completed")
        except Exception:
            pass
        return result
    except Exception as e:
        logger.exception("Auto-apply execution failed for user %s: %s", user_id, e)
        run.status = "failed"
        run.error_message = str(e)
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "error_message", "completed_at"])
        try:
            from agents.metrics import track_agent_run
            track_agent_run("auto_apply", trigger, "failed")
        except Exception:
            pass
        return {"error": str(e)}

logger = logging.getLogger(__name__)

class DigestState(TypedDict, total=False):
    user_id: int
    run_id: int
    candidate_jobs: List[Job]
    recommended_jobs: List[Dict[str, Any]]
    intro_text: str
    action_id: Optional[int]
    error: Optional[str]

def fetch_jobs_node(state: DigestState) -> Dict[str, Any]:
    user = User.objects.get(id=state["user_id"])
    sub = getattr(user, "digest_subscription", None)
    since_date = sub.last_sent_at if (sub and sub.last_sent_at) else (timezone.now() - timedelta(days=7))
    new_jobs = get_new_jobs_since(user, since_date)
    return {"candidate_jobs": new_jobs}

def score_filter_node(state: DigestState) -> Dict[str, Any]:
    user = User.objects.get(id=state["user_id"])
    sub = getattr(user, "digest_subscription", None)
    min_score = sub.min_score_threshold if sub else 70
    max_count = sub.max_jobs_per_digest if sub else 5
    candidate_jobs = state.get("candidate_jobs", [])
    scored: List[Dict[str, Any]] = []
    for job in candidate_jobs:
        score_data = score_candidate(user, job)
        score = score_data.get("overall_score", 0)
        if score >= min_score:
            reason = template_reason(job, score_data)
            scored.append({
                "job": job,
                "score": score,
                "reason": reason,
                "score_data": score_data,
            })
    scored.sort(key=lambda x: x["score"], reverse=True)
    recommended = scored[:max_count]
    return {"recommended_jobs": recommended}

def intro_node(state: DigestState) -> Dict[str, Any]:
    user = User.objects.get(id=state["user_id"])
    recommended = state.get("recommended_jobs", [])
    if not recommended:
        return {"intro_text": ""}
    intro = write_digest_intro(user.username, recommended)
    return {"intro_text": intro}

def dispatch_node(state: DigestState) -> Dict[str, Any]:
    recommended = state.get("recommended_jobs", [])
    if not recommended:
        return {"action_id": None}
    user = User.objects.get(id=state["user_id"])
    run = AgentRun.objects.get(id=state["run_id"])
    intro = state.get("intro_text", "")
    action = dispatch_digest(user, recommended, intro, run)
    return {"action_id": action.id if action else None}

def build_digest_graph():
    builder = StateGraph(DigestState)
    builder.add_node("fetch_jobs", fetch_jobs_node)
    builder.add_node("score_filter", score_filter_node)
    builder.add_node("intro", intro_node)
    builder.add_node("dispatch", dispatch_node)
    builder.set_entry_point("fetch_jobs")
    builder.add_edge("fetch_jobs", "score_filter")
    builder.add_edge("score_filter", "intro")
    builder.add_edge("intro", "dispatch")
    builder.add_edge("dispatch", END)
    return builder.compile()

digest_graph = build_digest_graph()

def execute_digest_agent(user_id: int, trigger: str = "scheduled") -> Dict[str, Any]:
    if not is_agent_enabled("digest"):
        logger.info("Digest agent is disabled by kill switch.")
        return {"error": "Digest agent is disabled."}
    user = User.objects.filter(id=user_id).first()
    if not user:
        return {"error": f"User {user_id} not found."}
    sub = getattr(user, "digest_subscription", None)
    if not sub or sub.frequency == "off":
        return {"skipped": "Subscription inactive or turned off"}
    run = AgentRun.objects.create(
        agent_type="digest",
        user=user,
        trigger=trigger,
        status="running",
    )
    try:
        initial_state: DigestState = {
            "user_id": user_id,
            "run_id": run.id,
        }
        result = digest_graph.invoke(initial_state)
        run.status = "completed"
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "completed_at"])
        try:
            from agents.metrics import track_agent_run
            track_agent_run("digest", trigger, "completed")
        except Exception:
            pass
        return result
    except Exception as e:
        logger.exception("Digest agent execution failed for user %s: %s", user_id, e)
        run.status = "failed"
        run.error_message = str(e)
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "error_message", "completed_at"])
        try:
            from agents.metrics import track_agent_run
            track_agent_run("digest", trigger, "failed")
        except Exception:
            pass
        return {"error": str(e)}

logger = logging.getLogger(__name__)

class SchedulingState(TypedDict, total=False):
    application_id: int
    run_id: int
    raw_slots: List[Dict[str, Any]]
    ranked_slots: List[Dict[str, Any]]
    proposal_id: Optional[int]
    error: Optional[str]

def fetch_slots_node(state: SchedulingState) -> Dict[str, Any]:
    app = Application.objects.select_related("job__recruiter").get(id=state["application_id"])
    recruiter = app.job.recruiter
    slots = get_recruiter_calendar_slots(recruiter)
    return {"raw_slots": slots}

def rank_slots_node(state: SchedulingState) -> Dict[str, Any]:
    app = Application.objects.select_related("job", "candidate").get(id=state["application_id"])
    raw_slots = state.get("raw_slots", [])
    ranked = rank_slots(
        slots=raw_slots,
        candidate_name=app.full_name or app.candidate.username,
        job_title=app.job.title,
    )
    return {"ranked_slots": ranked}

def propose_and_invite_node(state: SchedulingState) -> Dict[str, Any]:
    app = Application.objects.select_related("job", "candidate").get(id=state["application_id"])
    run = AgentRun.objects.get(id=state["run_id"])
    ranked = state.get("ranked_slots", [])
    proposal = create_slot_proposal(application=app, proposed_slots=ranked, run=run)
    send_slot_picker_email(proposal)
    return {"proposal_id": proposal.id}

def build_scheduling_graph():
    builder = StateGraph(SchedulingState)
    builder.add_node("fetch_slots", fetch_slots_node)
    builder.add_node("rank_slots", rank_slots_node)
    builder.add_node("propose_and_invite", propose_and_invite_node)
    builder.set_entry_point("fetch_slots")
    builder.add_edge("fetch_slots", "rank_slots")
    builder.add_edge("rank_slots", "propose_and_invite")
    builder.add_edge("propose_and_invite", END)
    return builder.compile()

scheduling_graph = build_scheduling_graph()

def execute_scheduling_agent(application_id: int, trigger: str = "event") -> Dict[str, Any]:
    if not is_agent_enabled("scheduling"):
        logger.info("Scheduling agent is disabled by kill switch.")
        return {"error": "Scheduling agent is disabled."}
    app = Application.objects.select_related("job", "candidate").filter(id=application_id).first()
    if not app:
        return {"error": f"Application {application_id} not found."}
    run = AgentRun.objects.create(
        agent_type="scheduling",
        user=app.candidate,
        trigger=trigger,
        status="running",
    )
    try:
        initial_state: SchedulingState = {
            "application_id": application_id,
            "run_id": run.id,
        }
        result = scheduling_graph.invoke(initial_state)
        run.status = "completed"
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "completed_at"])
        try:
            from agents.metrics import track_agent_run
            track_agent_run("scheduling", trigger, "completed")
        except Exception:
            pass
        return result
    except Exception as e:
        logger.exception("Scheduling agent execution failed for app %s: %s", application_id, e)
        run.status = "failed"
        run.error_message = str(e)
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "error_message", "completed_at"])
        try:
            from agents.metrics import track_agent_run
            track_agent_run("scheduling", trigger, "failed")
        except Exception:
            pass
        return {"error": str(e)}

logger = logging.getLogger(__name__)

class ScreeningState(TypedDict, total=False):
    application_id: int
    run_id: int
    score_data: Dict[str, Any]
    decision: str
    rationale: str
    auto_execute: bool
    action_id: Optional[int]
    error: Optional[str]

def score_node(state: ScreeningState) -> Dict[str, Any]:
    app = Application.objects.select_related("job", "candidate").get(id=state["application_id"])
    score_data = score_candidate(app, app.job)
    return {"score_data": score_data}

def classify_node(state: ScreeningState) -> Dict[str, Any]:
    app = Application.objects.select_related("job__recruiter").get(id=state["application_id"])
    recruiter = app.job.recruiter
    settings = ScreeningAgentSettings.objects.filter(recruiter=recruiter).first()
    score = state["score_data"].get("overall_score", 50)
    decision = classify_score(score, settings)
    auto_execute = False
    if settings and settings.auto_execute_extreme_scores and decision in ("shortlist", "reject"):
        auto_execute = True
    return {"decision": decision, "auto_execute": auto_execute}

def rationale_node(state: ScreeningState) -> Dict[str, Any]:
    app = Application.objects.select_related("job").get(id=state["application_id"])
    score_data = state["score_data"]
    rationale = write_rationale(
        candidate_name=app.full_name or app.candidate.username,
        job_title=app.job.title,
        score=score_data.get("overall_score", 50),
        decision=state["decision"],
        matching_points=score_data.get("matching_points", []),
        gaps=score_data.get("gaps", []),
    )
    return {"rationale": rationale}

def apply_node(state: ScreeningState) -> Dict[str, Any]:
    app = Application.objects.get(id=state["application_id"])
    run = AgentRun.objects.get(id=state["run_id"])
    score = state["score_data"].get("overall_score", 50)
    action = apply_screening_decision(
        application=app,
        decision=state["decision"],
        score=score,
        rationale=state["rationale"],
        auto_execute=state.get("auto_execute", False),
        run=run,
    )
    return {"action_id": action.id}

def build_screening_graph():
    builder = StateGraph(ScreeningState)
    builder.add_node("score", score_node)
    builder.add_node("classify", classify_node)
    builder.add_node("rationale", rationale_node)
    builder.add_node("apply", apply_node)
    builder.set_entry_point("score")
    builder.add_edge("score", "classify")
    builder.add_edge("classify", "rationale")
    builder.add_edge("rationale", "apply")
    builder.add_edge("apply", END)
    return builder.compile()

screening_graph = build_screening_graph()

def execute_screening_agent(application_id: int, trigger: str = "event") -> Dict[str, Any]:
    if not is_agent_enabled("screening"):
        logger.info("Screening agent is disabled by kill switch.")
        return {"error": "Screening agent is disabled."}
    app = Application.objects.select_related("job", "candidate").filter(id=application_id).first()
    if not app:
        return {"error": f"Application {application_id} not found."}
    recruiter = app.job.recruiter
    settings = ScreeningAgentSettings.objects.filter(recruiter=recruiter).first()
    if settings and not settings.enabled:
        logger.info("Screening agent disabled for recruiter %s", recruiter)
        return {"skipped": "Recruiter disabled screening"}
    run = AgentRun.objects.create(
        agent_type="screening",
        user=app.candidate,
        trigger=trigger,
        status="running",
    )
    try:
        initial_state: ScreeningState = {
            "application_id": application_id,
            "run_id": run.id,
        }
        result = screening_graph.invoke(initial_state)
        run.status = "completed"
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "completed_at"])
        try:
            from agents.metrics import track_agent_run
            track_agent_run("screening", trigger, "completed")
        except Exception:
            pass
        return result
    except Exception as e:
        logger.exception("Screening agent execution failed: %s", e)
        run.status = "failed"
        run.error_message = str(e)
        run.completed_at = timezone.now()
        run.save(update_fields=["status", "error_message", "completed_at"])
        try:
            from agents.metrics import track_agent_run
            track_agent_run("screening", trigger, "failed")
        except Exception:
            pass
        return {"error": str(e)}
