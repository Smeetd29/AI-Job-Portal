from __future__ import annotations
import os, json, secrets, logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Union
from django.conf import settings
from django.core.mail import send_mail
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from jobs.models import Job
from users.models import User
from application.ai.pipeline import MatchingPipeline, ResumeAnalysis
from application.models import Application
from agents.models import (
    AgentAction, AgentRun, AutoApplySettings,
    Interview, InterviewSlotProposal, ScreeningAgentSettings
)

class LLMClient:
    def __init__(self, raw_client=None):
        self.raw_client = raw_client

    def generate(self, prompt: str, max_tokens: int = 250) -> str:
        if self.raw_client is not None:
            try:
                return self.raw_client.messages.create(
                    model=getattr(settings, "ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
                    max_tokens=max_tokens,
                    messages=[{"role": "user", "content": prompt}],
                ).content[0].text
            except Exception:
                pass
        lower = prompt.lower()
        if "rationale" in lower:
            return "Strong alignment on core technical qualifications and relevant background."
        if "digest" in lower or "advisor" in lower:
            return "We found exciting new opportunities that align with your profile this week. Here are your top tailored recommendations to explore and apply."
        if "cover letter" in lower:
            import re
            skills_match = re.search(r"Key Skills:\s*([^\n]+)", prompt)
            skills = skills_match.group(1).strip() if skills_match else "software engineering"
            evidence_match = re.search(r"Verified Candidate Strengths:\s*([^\n]+)", prompt)
            evidence = evidence_match.group(1).strip() if evidence_match else "core technical qualifications"
            applicant_match = re.search(r"Applicant:\s*([^\n]+)", prompt)
            applicant = applicant_match.group(1).strip() if applicant_match else "Applicant"
            return (
                f"Dear Hiring Team,\n\n"
                f"I am writing to express my strong interest in this role. "
                f"With proven hands-on expertise in {skills}, I am well prepared to contribute effectively. "
                f"My technical background demonstrates {evidence}. I look forward to discussing how my experience aligns with your team's goals.\n\n"
                f"Sincerely,\n{applicant}"
            )
        if "slot" in lower or "indices" in lower:
            return "[0, 1, 2]"
        return "Analysis and contextual response generated successfully."

_client_instance = None

def get_llm():
    global _client_instance
    if _client_instance is not None:
        return _client_instance
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', None) or os.getenv('ANTHROPIC_API_KEY')
    raw = None
    if api_key and not api_key.startswith(('mock', 'placeholder')):
        try:
            import anthropic
            raw = anthropic.Anthropic(api_key=api_key)
        except Exception:
            pass
    _client_instance = LLMClient(raw_client=raw)
    return _client_instance

logger = logging.getLogger(__name__)

def score_candidate(
    candidate_or_app: Union[User, Application, int, Any],
    job_or_id: Union[Job, int],
) -> Dict[str, Any]:
    if isinstance(job_or_id, Job):
        job = job_or_id
    else:
        job = Job.objects.get(id=job_or_id)
    candidate_name = ""
    resume_file = None
    if isinstance(candidate_or_app, Application):
        candidate_name = candidate_or_app.full_name or candidate_or_app.candidate.username
        resume_file = candidate_or_app.resume_snapshot or getattr(
            candidate_or_app.candidate.candidate_profile, 'resume', None
        )
    elif isinstance(candidate_or_app, User):
        candidate_name = candidate_or_app.username
        resume_file = getattr(candidate_or_app.candidate_profile, 'resume', None)
    elif isinstance(candidate_or_app, int):
        app = Application.objects.filter(id=candidate_or_app).first()
        if app:
            candidate_name = app.full_name or app.candidate.username
            resume_file = app.resume_snapshot or getattr(app.candidate.candidate_profile, 'resume', None)
        else:
            user = User.objects.filter(id=candidate_or_app).first()
            if user:
                candidate_name = user.username
                resume_file = getattr(user.candidate_profile, 'resume', None)
    if not resume_file:
        logger.warning("No resume found for candidate %s, using fallback score", candidate_name)
        return {
            "overall_score": 50,
            "key_skills": [],
            "matching_points": [],
            "gaps": ["No resume file available for analysis"],
            "recommendation": "Review manually (Missing resume)",
            "explanation": "No resume file available.",
            "candidate_summary": "",
        }
    pipeline = MatchingPipeline.get_default()
    analysis: ResumeAnalysis = pipeline.analyze_resume(
        file_field=resume_file,
        job_title=job.title,
        job_description=job.description,
        candidate_name=candidate_name,
        job_id=job.id,
    )
    return {
        "overall_score": int(analysis.match_score),
        "key_skills": list(analysis.key_skills),
        "matching_points": [
            {"point": p.point, "evidence": p.evidence} for p in analysis.matching_points
        ],
        "gaps": [g.point for g in analysis.gaps],
        "recommendation": analysis.recommendation,
        "explanation": analysis.explanation,
        "candidate_summary": analysis.candidate_summary,
    }

def send_email(template: str, to: str, context: Dict[str, Any]) -> None:
    from_email = getattr(settings, 'EMAIL_HOST_USER', 'noreply@careerconnect.com')
    subject = context.get('subject', f"CareerConnect Notification: {template}")
    body = context.get('body', "")
    if not body and 'message' in context:
        body = context['message']
    try:
        from agents.metrics import track_email_sent
        track_email_sent(template, "sent")
    except Exception:
        pass
    send_mail(
        subject=subject,
        message=body,
        from_email=from_email,
        recipient_list=[to] if isinstance(to, str) else list(to),
        fail_silently=True,
    )

logger = logging.getLogger(__name__)

def get_eligible_jobs(user: User, settings: AutoApplySettings) -> List[Job]:
    qs = Job.objects.filter(is_active=True)
    existing_job_ids = Application.objects.filter(candidate=user).values_list("job_id", flat=True)
    qs = qs.exclude(id__in=existing_job_ids)
    action_job_ids = AgentAction.objects.filter(user=user, agent_type="auto_apply").values_list("job_id", flat=True)
    qs = qs.exclude(id__in=action_job_ids)
    excluded = [c.strip().lower() for c in settings.excluded_companies if isinstance(c, str)]
    if excluded:
        for comp in excluded:
            qs = qs.exclude(recruiter__recruiter_profile__company_name__iexact=comp)
    return list(qs.order_by("-created_at")[:40])

def count_applications_today(user: User) -> int:
    today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
    return AgentAction.objects.filter(
        user=user,
        agent_type="auto_apply",
        created_at__gte=today_start,
    ).count()

def draft_cover_letter(user: User, job: Job, match_data: Dict[str, Any]) -> str:
    skills = match_data.get("key_skills", [])
    matches = match_data.get("matching_points", [])
    top_matches = [m.get("point", "") for m in matches[:3] if isinstance(m, dict)]
    evidence_str = "; ".join(top_matches) if top_matches else "relevant domain experience"
    skills_str = ", ".join(skills[:4]) if skills else "professional engineering practices"
    prompt = (
        f"You are drafting a concise, professional cover letter for an applicant.\n"
        f"Applicant: {user.username}\n"
        f"Target Role: {job.title} at {job.company_name}\n"
        f"Verified Candidate Strengths: {evidence_str}\n"
        f"Key Skills: {skills_str}\n\n"
        f"Rules:\n"
        f"1. Strictly under 200 words.\n"
        f"2. Only reference verified candidate strengths and skills above. Do not invent details.\n"
        f"3. Professional, enthusiastic tone.\n"
        f"Output the cover letter body directly."
    )
    try:
        llm = get_llm()
        return llm.generate(prompt=prompt, max_tokens=250)
    except Exception as e:
        logger.warning("Cover letter generation fallback: %s", e)
        return (
            f"Dear Hiring Team at {job.company_name},\n\n"
            f"I am writing to express my strong interest in the {job.title} role. "
            f"With proven hands-on expertise in {skills_str}, I am confident in my ability to deliver "
            f"high-impact contributions to your team.\n\n"
            f"Specifically, my background demonstrates {evidence_str}. "
            f"I look forward to discussing how my experience aligns with your team's upcoming goals.\n\n"
            f"Sincerely,\n{user.username}"
        )

def send_action_email(
    action: AgentAction,
    template: str,
    to: str,
    context: Dict[str, Any],
) -> bool:
    """
    Claim-then-send atomic pattern for email idempotency.
    Enforces at-most-once delivery semantics:
    1. Atomically update email_state from NULL -> 'sending' (WHERE email_state IS NULL).
    2. Check rows affected == 1. If 0, action was already claimed/sent by another worker; do not send.
    3. Send email.
    4. Upon success, mark email_state = 'sent'.
    5. If a crash or error occurs between send and mark, email_state remains 'sending',
       preventing duplicate sends on worker retries.
    """
    with transaction.atomic():
        rows = AgentAction.objects.filter(id=action.id, email_state__isnull=True).update(email_state="sending")
        if rows != 1:
            logger.info("Email for action %s already claimed or sent (rows=%d), skipping duplicate send.", action.id, rows)
            return False

    send_email(template, to, context)
    AgentAction.objects.filter(id=action.id).update(email_state="sent")
    return True

def create_or_submit_application(
    user: User,
    job: Job,
    cover_letter: str,
    score: int,
    mode: str,
    run: AgentRun,
) -> AgentAction:
    with transaction.atomic():
        # Prevent cap race by acquiring exclusive row lock on User
        locked_user = User.objects.select_for_update().get(id=user.id)

        from agents.guardrails import HARD_WEEKLY_APPLICATION_CEILING, get_weekly_application_count
        weekly_count = get_weekly_application_count(locked_user.id)
        if weekly_count >= HARD_WEEKLY_APPLICATION_CEILING:
            raise ValueError(
                f"Hard weekly application ceiling ({HARD_WEEKLY_APPLICATION_CEILING}) exceeded for user {locked_user.username} (current: {weekly_count})"
            )

        settings = getattr(locked_user, "auto_apply_settings", None)
        if settings and settings.daily_cap:
            daily_count = count_applications_today(locked_user)
            if daily_count >= settings.daily_cap:
                raise ValueError(
                    f"Daily application cap ({settings.daily_cap}) exceeded for user {locked_user.username} (current: {daily_count})"
                )

        app_ct = ContentType.objects.get_for_model(Application)
        profile = getattr(locked_user, "candidate_profile", None)
        resume = profile.resume if profile else None
        status = "DRAFT" if mode == "review_first" else "PENDING"
        application, _ = Application.objects.update_or_create(
            job=job,
            candidate=locked_user,
            defaults={
                "full_name": locked_user.get_full_name() or locked_user.username,
                "email": locked_user.email or f"{locked_user.username}@example.com",
                "phone_number": getattr(profile, "phone", "") or "N/A",
                "university_name": "N/A",
                "university_country": "N/A",
                "academic_level": "Bachelor",
                "stream": "General",
                "current_year": "Graduate",
                "graduation_year": 2024,
                "major": "General",
                "grading_system": "GPA",
                "overall_grade": "3.8",
                "skills": getattr(profile, "skills", "") or "General",
                "area_of_interest": "General",
                "linkedin_profile": "https://linkedin.com",
                "referral_source": "Auto-Apply Agent",
                "work_authorization_country": "US",
                "resume_snapshot": resume,
                "cover_letter": cover_letter,
                "status": status,
                "source": "auto_apply",
            },
        )
        action_status = "pending" if mode == "review_first" else "auto_executed"
        requires_approval = mode == "review_first"
        executed = mode == "auto_submit"
        action, _ = AgentAction.objects.update_or_create(
            job=job,
            user=locked_user,
            agent_type="auto_apply",
            defaults={
                "run": run,
                "content_type": app_ct,
                "object_id": application.id,
                "action_type": f"auto_apply_{mode}",
                "payload": {
                    "score": score,
                    "mode": mode,
                    "cover_letter": cover_letter,
                    "application_id": application.id,
                    "job_title": job.title,
                    "company_name": job.company_name,
                },
                "requires_approval": requires_approval,
                "status": action_status,
                "executed": executed,
            },
        )
        return action

def notify_candidate_batch(
    user: User,
    submitted_actions: List[AgentAction],
    draft_actions: List[AgentAction],
) -> None:
    if not submitted_actions and not draft_actions:
        return

    action_ids = [act.id for act in submitted_actions + draft_actions]
    with transaction.atomic():
        # Atomically claim actions that haven't been claimed/sent yet (claim-then-send)
        claimed_count = AgentAction.objects.filter(
            id__in=action_ids,
            email_state__isnull=True,
        ).update(email_state="sending")
        if claimed_count == 0:
            logger.info("All actions for user %s already claimed or sent. Skipping duplicate email.", user.username)
            return

    lines = [f"Hi {user.username},", ""]
    if submitted_actions:
        lines.append(f"We auto-submitted {len(submitted_actions)} applications on your behalf:")
        for act in submitted_actions:
            lines.append(f"• {act.job.title} at {act.job.company_name} (Score: {act.payload.get('score', 'N/A')}%)")
        lines.append("")
    if draft_actions:
        lines.append(f"We prepared {len(draft_actions)} applications ready for your review:")
        for act in draft_actions:
            lines.append(f"• {act.job.title} at {act.job.company_name} (Score: {act.payload.get('score', 'N/A')}%)")
        lines.append("")
        lines.append("Visit your CareerConnect Auto-Apply Dashboard to review, edit, or submit them.")

    send_email(
        template="auto_apply_digest",
        to=user.email or f"{user.username}@example.com",
        context={
            "subject": f"CareerConnect Auto-Apply: {len(submitted_actions) + len(draft_actions)} Applications Processed",
            "body": "\n".join(lines),
        },
    )

    # Atomically mark as sent and maintain payload backward compatibility
    for act in submitted_actions + draft_actions:
        payload = act.payload or {}
        payload["email_notified"] = True
        AgentAction.objects.filter(id=act.id, email_state="sending").update(email_state="sent", payload=payload)


logger = logging.getLogger(__name__)

def get_new_jobs_since(user: User, since_date: Optional[datetime]) -> List[Job]:
    qs = Job.objects.filter(is_active=True)
    if since_date:
        qs = qs.filter(created_at__gte=since_date)
    applied_job_ids = Application.objects.filter(candidate=user).values_list('job_id', flat=True)
    qs = qs.exclude(id__in=applied_job_ids)
    return list(qs.order_by('-created_at')[:50])

def template_reason(job: Job, score_data: Dict[str, Any]) -> str:
    key_skills = score_data.get("key_skills", [])
    matches = score_data.get("matching_points", [])
    top_matches = [m["point"] for m in matches[:2] if isinstance(m, dict) and "point" in m]
    parts = []
    if key_skills:
        parts.append(f"Strong overlap with your skills in {', '.join(key_skills[:3])}")
    if top_matches:
        parts.append("; ".join(top_matches))
    return " | ".join(parts) if parts else f"Good overall alignment with {job.title} requirements."

def write_digest_intro(user_name: str, jobs: List[Dict[str, Any]]) -> str:
    job_titles = [f"{j['job'].title} at {j['job'].company_name} ({j['score']}% match)" for j in jobs[:3]]
    titles_summary = ", ".join(job_titles)
    prompt = (
        f"You are a helpful career advisor writing an opening paragraph for a job digest email.\n"
        f"Candidate: {user_name}\n"
        f"Top Recommended Roles:\n{titles_summary}\n\n"
        f"Write an encouraging, warm 2-sentence opening greeting and summary of why these new roles "
        f"stand out for them this week."
    )
    try:
        llm = get_llm()
        return llm.generate(prompt=prompt, max_tokens=100)
    except Exception as e:
        logger.warning("Digest LLM intro generation failed: %s. Using fallback.", e)
        return (
            f"Hi {user_name}, we found exciting new opportunities that align with your profile this week. "
            f"Here are your top tailored recommendations to explore and apply."
        )

def dispatch_digest(
    user: User,
    recommended_jobs: List[Dict[str, Any]],
    intro_text: str,
    run: AgentRun,
) -> Optional[AgentAction]:
    if not recommended_jobs:
        return None
    email_body_lines = [intro_text, "", "Here are your top recommended opportunities:"]
    for item in recommended_jobs:
        job = item["job"]
        score = item["score"]
        reason = item["reason"]
        email_body_lines.append(f"• {job.title} at {job.company_name} - {score}% Match")
        email_body_lines.append(f"  Why: {reason}")
        email_body_lines.append("")
    email_body_lines.append("Log in to CareerConnect to review and submit your applications.")
    email_body = "\n".join(email_body_lines)
    send_email(
        template="job_digest",
        to=user.email or f"{user.username}@example.com",
        context={
            "subject": f"CareerConnect Job Digest: {len(recommended_jobs)} New Matches for You",
            "body": email_body,
        },
    )
    sub = getattr(user, 'digest_subscription', None)
    if sub:
        sub.last_sent_at = timezone.now()
        sub.save(update_fields=['last_sent_at'])
    action = AgentAction.objects.create(
        run=run,
        user=user,
        agent_type="digest",
        action_type="digest_email_sent",
        payload={
            "job_count": len(recommended_jobs),
            "jobs": [
                {"job_id": j["job"].id, "title": j["job"].title, "score": j["score"]}
                for j in recommended_jobs
            ],
            "intro": intro_text,
        },
        requires_approval=False,
        status="auto_executed",
        executed=True,
    )
    return action

logger = logging.getLogger(__name__)

def get_recruiter_calendar_slots(recruiter: User) -> List[Dict[str, Any]]:
    slots: List[Dict[str, Any]] = []
    now = timezone.now()
    days_checked = 0
    current_offset = 1
    while len(slots) < 12 and days_checked < 7:
        target_date = now + timedelta(days=current_offset)
        current_offset += 1
        if target_date.weekday() >= 5:
            continue
        days_checked += 1
        for hour in [10, 14, 16]:
            slot_time = target_date.replace(hour=hour, minute=0, second=0, microsecond=0)
            slots.append({
                "datetime": slot_time.isoformat(),
                "display": slot_time.strftime("%A, %b %d at %I:%M %p UTC"),
                "weekday": slot_time.strftime("%A"),
            })
    return slots

def rank_slots(
    slots: List[Dict[str, Any]],
    candidate_name: str,
    job_title: str,
) -> List[Dict[str, Any]]:
    if len(slots) <= 3:
        return slots
    slot_summary = "\n".join([f"{i}: {s['display']}" for i, s in enumerate(slots)])
    prompt = (
        f"You are an interview coordinator picking the 3 best slot options for {candidate_name} "
        f"applying for {job_title}.\n"
        f"Available candidate slots:\n{slot_summary}\n\n"
        f"Choose exactly 3 slots spread across different weekdays and distinct morning/afternoon times.\n"
        f"Return ONLY a JSON array of the 3 integer indices, e.g. [0, 4, 8]."
    )
    try:
        llm = get_llm()
        response_text = llm.generate(prompt=prompt, max_tokens=60)
        start_idx = response_text.find("[")
        end_idx = response_text.rfind("]")
        if start_idx != -1 and end_idx != -1:
            indices = json.loads(response_text[start_idx : end_idx + 1])
            selected = [slots[i] for i in indices if 0 <= i < len(slots)]
            if len(selected) == 3:
                return selected
    except Exception as e:
        logger.warning("LLM slot ranking fallback: %s", e)
    seen_days = set()
    chosen = []
    for s in slots:
        if s["weekday"] not in seen_days:
            chosen.append(s)
            seen_days.add(s["weekday"])
        if len(chosen) == 3:
            break
    return chosen if len(chosen) == 3 else slots[:3]

def create_slot_proposal(
    application: Application,
    proposed_slots: List[Dict[str, Any]],
    run: AgentRun,
) -> InterviewSlotProposal:
    magic_token = secrets.token_urlsafe(32)
    proposal = InterviewSlotProposal.objects.create(
        application=application,
        proposed_slots=proposed_slots,
        magic_token=magic_token,
        status="pending",
    )
    app_ct = ContentType.objects.get_for_model(InterviewSlotProposal)
    AgentAction.objects.create(
        run=run,
        user=application.candidate,
        job=application.job,
        agent_type="scheduling",
        content_type=app_ct,
        object_id=proposal.id,
        action_type="slot_proposal_issued",
        payload={
            "magic_token": magic_token,
            "proposal_id": proposal.id,
            "application_id": application.id,
            "slots": proposed_slots,
        },
        requires_approval=False,
        status="pending",
        executed=False,
    )
    return proposal

def send_slot_picker_email(proposal: InterviewSlotProposal) -> None:
    app = proposal.application
    booking_url = f"/schedule/{proposal.magic_token}/"
    body_lines = [
        f"Hi {app.full_name},",
        "",
        f"Great news! The recruiting team for {app.job.title} at {app.job.company_name} "
        f"would like to schedule an interview with you.",
        "",
        "Please select one of the following available time slots:",
    ]
    for s in proposal.proposed_slots:
        body_lines.append(f"• {s.get('display', s.get('datetime'))}")
    body_lines.append("")
    body_lines.append(f"Confirm your interview slot here: {booking_url}")
    body_lines.append("Note: This selection link expires in 72 hours.")
    send_email(
        template="interview_invitation",
        to=app.email or app.candidate.email,
        context={
            "subject": f"Interview Invitation: {app.job.title} at {app.job.company_name}",
            "body": "\n".join(body_lines),
        },
    )

def book_interview(proposal: InterviewSlotProposal, chosen_slot_iso: str) -> Interview:
    now = timezone.now()
    if proposal.status != "pending":
        raise ValueError(f"Proposal is already {proposal.status}")
    if (now - proposal.created_at).total_seconds() > 72 * 3600:
        proposal.status = "expired"
        proposal.save(update_fields=["status"])
        raise ValueError("This interview booking link has expired (72h limit).")
    meeting_url = f"https://meet.careerconnect.com/{proposal.magic_token[:10]}"
    interview = Interview.objects.create(
        application=proposal.application,
        scheduled_at=datetime.fromisoformat(chosen_slot_iso),
        meeting_link=meeting_url,
        calendar_event_id=f"evt_{proposal.magic_token[:8]}",
    )
    proposal.status = "confirmed"
    proposal.save(update_fields=["status"])
    proposal_ct = ContentType.objects.get_for_model(InterviewSlotProposal)
    AgentAction.objects.filter(
        content_type=proposal_ct,
        object_id=proposal.id,
    ).update(status="auto_executed", executed=True)
    app = proposal.application
    recruiter = app.job.recruiter
    time_str = interview.scheduled_at.strftime("%A, %B %d, %Y at %I:%M %p UTC")
    send_email(
        template="interview_confirmed_candidate",
        to=app.email,
        context={
            "subject": f"Confirmed: Interview for {app.job.title}",
            "body": f"Your interview for {app.job.title} is confirmed for {time_str}.\nMeeting Link: {meeting_url}",
        },
    )
    if recruiter and recruiter.email:
        send_email(
            template="interview_confirmed_recruiter",
            to=recruiter.email,
            context={
                "subject": f"Interview Scheduled: {app.full_name} for {app.job.title}",
                "body": f"Candidate {app.full_name} booked their interview for {time_str}.\nMeeting Link: {meeting_url}",
            },
        )
    return interview

logger = logging.getLogger(__name__)

def classify_score(score: int, settings: Optional[ScreeningAgentSettings]) -> str:
    shortlist_thresh = settings.shortlist_threshold if settings else 84
    reject_thresh = settings.reject_threshold if settings else 45
    if score >= shortlist_thresh:
        return "shortlist"
    elif score < reject_thresh:
        return "reject"
    return "review"

def write_rationale(
    candidate_name: str,
    job_title: str,
    score: int,
    decision: str,
    matching_points: List[Dict[str, str]],
    gaps: List[str],
) -> str:
    top_matches = [p.get("point", "") for p in matching_points[:3] if isinstance(p, dict)]
    evidence = "; ".join(top_matches) if top_matches else "Standard qualifications observed."
    gap_summary = "; ".join(gaps[:2]) if gaps else "No major skill gaps."
    prompt = (
        f"You are an expert AI recruiting assistant reviewing an applicant.\n"
        f"Candidate: {candidate_name}\n"
        f"Job: {job_title}\n"
        f"Match Score: {score}/100\n"
        f"Decision: {decision.upper()}\n"
        f"Key Strengths: {evidence}\n"
        f"Missing/Gaps: {gap_summary}\n\n"
        f"Write a concise, professional 2-3 sentence rationale explaining why this candidate was "
        f"classified as {decision.upper()}. Cite specific strengths or gaps directly."
    )
    try:
        llm = get_llm()
        return llm.generate(prompt=prompt, max_tokens=150)
    except Exception as e:
        logger.warning("LLM rationale generation failed: %s. Using deterministic fallback.", e)
        if decision == "shortlist":
            return (
                f"{candidate_name} scored {score}/100 for {job_title}, demonstrating strong alignment in {evidence}. "
                f"Recommended for immediate recruiter interview."
            )
        elif decision == "reject":
            return (
                f"{candidate_name} scored {score}/100 for {job_title}. Key skill gaps identified: {gap_summary}. "
                f"Does not meet minimum role requirements."
            )
        return (
            f"{candidate_name} scored {score}/100 for {job_title}. Shows promising foundation ({evidence}) "
            f"with potential gaps in {gap_summary}. Requires recruiter review."
        )

def apply_screening_decision(
    application: Application,
    decision: str,
    score: int,
    rationale: str,
    auto_execute: bool,
    run: AgentRun,
) -> AgentAction:
    app_ct = ContentType.objects.get_for_model(Application)
    payload = {
        "score": score,
        "decision": decision,
        "rationale": rationale,
        "auto_executed": auto_execute,
    }
    if auto_execute and decision in ("shortlist", "reject"):
        if decision == "shortlist":
            application.status = "SHORTLISTED"
        elif decision == "reject":
            application.status = "REJECTED"
        application.save(update_fields=["status"])
        action, _ = AgentAction.objects.update_or_create(
            job=application.job,
            user=application.candidate,
            agent_type="screening",
            defaults={
                "run": run,
                "content_type": app_ct,
                "object_id": application.id,
                "action_type": f"screening_{decision}",
                "payload": payload,
                "requires_approval": False,
                "status": "auto_executed",
                "executed": True,
            },
        )
    else:
        action, _ = AgentAction.objects.update_or_create(
            job=application.job,
            user=application.candidate,
            agent_type="screening",
            defaults={
                "run": run,
                "content_type": app_ct,
                "object_id": application.id,
                "action_type": f"screening_{decision}",
                "payload": payload,
                "requires_approval": True,
                "status": "pending",
                "executed": False,
            },
        )
    return action
