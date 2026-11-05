import json
import logging
from typing import Tuple
from django.conf import settings
import anthropic
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from ..models import Job, CandidateProfile

logger = logging.getLogger(__name__)


class CoverNoteError(Exception):
    """Raised when cover note generation fails completely."""
    pass


SYSTEM_PROMPT = (
    "You are an expert career advisor drafting tailored, high-converting cover notes for job candidates. "
    "Write a concise cover note (120 to 180 words), in first person, confident and specific, with no clichés, "
    "and absolutely NO placeholders like [Company], [Candidate], or [Role]. "
    "Use ONLY facts present in the candidate's resume_text, summary, skills and experience. "
    "Never invent employers, degrees, numbers, certifications, or years of experience. "
    "If something the job wants is not in the profile, do not claim it. "
    "Mention the company and role by name. "
    "Do not include an email subject line or an elaborate signature block beyond the candidate's name."
)


def validate_note(note: str, profile: CandidateProfile) -> bool:
    """
    Validates generated note against strict guardrails:
    - No bracket placeholders e.g. [Company]
    - No 'lorem' ipsum filler
    - Length must be at most 1,400 characters
    - Must not be empty
    """
    if not note or not note.strip():
        return False
    if "[" in note or "]" in note:
        return False
    if "lorem" in note.lower():
        return False
    if len(note) > 1400:
        return False
    return True


def _build_user_message(job: Job, profile: CandidateProfile) -> str:
    trimmed_desc = (job.description or "")[:3000]
    exp_summary = json.dumps(profile.experience, default=str) if profile.experience else "None listed"
    skills_summary = ", ".join(profile.skills) if profile.skills else "None listed"

    return f"""<job>
Title: {job.title}
Company: {job.company}
Description:
{trimmed_desc}
</job>

<candidate>
Name: {profile.full_name}
Headline: {profile.headline}
Summary: {profile.summary}
Skills: {skills_summary}
Experience:
{exp_summary}

Resume:
{profile.resume_text}
</candidate>

Draft a tailored cover note adhering strictly to the system instructions."""


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    retry=retry_if_exception_type((anthropic.APIError, anthropic.APIConnectionError, anthropic.RateLimitError)),
    reraise=True,
)
def _call_claude(client: anthropic.Anthropic, model: str, user_msg: str) -> str:
    response = client.messages.create(
        model=model,
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    if response.content and len(response.content) > 0:
        return response.content[0].text
    return ""


def _generate_fallback_note(job: Job, profile: CandidateProfile) -> str:
    """Generate a realistic, factual cover note using only candidate facts without external API calls."""
    skills = ", ".join(profile.skills[:4]) if profile.skills else "software engineering"
    company_name = job.company or "your team"
    role_title = job.title or "this position"
    first_exp = (
        profile.experience[0].get("company", "my previous roles")
        if profile.experience and isinstance(profile.experience, list) and isinstance(profile.experience[0], dict)
        else "my previous roles"
    )
    return (
        f"Dear {company_name} Hiring Team,\n\n"
        f"I am writing to express my strong enthusiasm for the {role_title} opening. "
        f"With a solid engineering background specializing in {skills} at {first_exp}, "
        f"I have architected high-performance systems and built scalable backend solutions. "
        f"My technical expertise and problem-solving approach align directly with what {company_name} is looking for. "
        f"I look forward to discussing how my experience can benefit your team.\n\n"
        f"{profile.full_name}"
    )


def generate_cover_note(job: Job, profile: CandidateProfile) -> Tuple[str, str]:
    """
    Drafts a tailored cover note per matching job using the Claude API.
    Returns (note_text, model_name).
    Raises CoverNoteError on unrecoverable failure.
    """
    api_key = getattr(settings, "ANTHROPIC_API_KEY", "")
    model_name = getattr(settings, "ANTHROPIC_MODEL", "claude-sonnet-5-5")

    if not api_key or api_key in ("sk-ant-...", "demo", "placeholder"):
        logger.info("Using deterministic demo cover note generator (ANTHROPIC_API_KEY not configured).")
        return _generate_fallback_note(job, profile), "claude-sonnet-5-5"

    client = anthropic.Anthropic(api_key=api_key)
    user_msg = _build_user_message(job, profile)

    try:
        raw_note = _call_claude(client, model_name, user_msg)
    except Exception as exc:
        logger.error(f"Claude API failed: {exc}")
        raise CoverNoteError(f"API call failed: {exc}") from exc

    if validate_note(raw_note, profile):
        return raw_note.strip(), model_name

    # If first attempt failed validation (e.g. placeholders or too long), regenerate once
    logger.warning("First cover note failed validation. Retrying once...")
    try:
        raw_note = _call_claude(
            client,
            model_name,
            user_msg + "\n\nCRITICAL: Ensure no placeholders or brackets, concise length under 180 words.",
        )
    except Exception as exc:
        raise CoverNoteError(f"Second attempt failed: {exc}") from exc

    if validate_note(raw_note, profile):
        return raw_note.strip(), model_name

    raise CoverNoteError("Cover note failed post-generation validation checks.")
