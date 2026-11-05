import re
import difflib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Set, Union
from ..models import Job, JobPreference, CandidateProfile
from ..sources.base import JobDTO


@dataclass
class MatchResult:
    passed: bool
    score: float  # 0..1
    reasons: List[str]  # human-readable, shown in the queue UI
    rejected_because: Optional[str] = None


def _clean_tokens(text: str) -> Set[str]:
    """Lowercase and strip punctuation into a set of word tokens."""
    if not text:
        return set()
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return {w for w in cleaned.split() if w}


def _compute_title_similarity(job_title: str, target_titles: List[str]) -> tuple[float, str]:
    """
    Compute title similarity vs target_titles using token overlap (Jaccard)
    and SequenceMatcher as a tiebreak. Returns (best_score, best_target_title).
    """
    if not target_titles:
        return 1.0, ""

    job_tokens = _clean_tokens(job_title)
    best_score = 0.0
    best_target = target_titles[0]

    for target in target_titles:
        target_tokens = _clean_tokens(target)
        if not target_tokens or not job_tokens:
            continue

        intersection = len(job_tokens & target_tokens)
        union = len(job_tokens | target_tokens)
        jaccard = intersection / union if union > 0 else 0.0

        seq_ratio = difflib.SequenceMatcher(
            None, job_title.strip().lower(), target.strip().lower()
        ).ratio()

        score = (0.8 * jaccard) + (0.2 * seq_ratio)
        if score > best_score:
            best_score = score
            best_target = target

    return round(best_score, 4), best_target


def evaluate(
    job: Union[Job, JobDTO],
    pref: JobPreference,
    profile: CandidateProfile,
) -> MatchResult:
    """
    Evaluates a job against a candidate's preferences and profile.
    Enforces hard filters in order and calculates soft match score.
    """
    reasons: List[str] = []

    # 1. Company exclusion
    job_company_clean = (job.company or "").strip().lower()
    exclude_companies = [c.strip().lower() for c in (pref.exclude_companies or []) if c.strip()]
    if job_company_clean and job_company_clean in exclude_companies:
        return MatchResult(
            passed=False,
            score=0.0,
            reasons=[],
            rejected_because=f"Company '{job.company}' is in your excluded companies list",
        )

    # 2. Exclude keywords in title or description
    job_text = f"{job.title} {job.description}".lower()
    exclude_keywords = [k.strip().lower() for k in (pref.exclude_keywords or []) if k.strip()]
    for kw in exclude_keywords:
        if re.search(r"\b" + re.escape(kw) + r"\b", job_text):
            return MatchResult(
                passed=False,
                score=0.0,
                reasons=[],
                rejected_because=f"Job contains excluded keyword '{kw}'",
            )

    # 3. Work mode
    job_mode = (job.work_mode or "unknown").strip().lower()
    target_modes = [m.strip().lower() for m in (pref.work_modes or []) if m.strip()]
    if target_modes and job_mode != "unknown" and job_mode not in target_modes:
        return MatchResult(
            passed=False,
            score=0.0,
            reasons=[],
            rejected_because=f"Work mode '{job_mode}' not in target modes: {', '.join(target_modes)}",
        )

    # 4. Location (for hybrid/onsite)
    if job_mode in ("hybrid", "onsite"):
        target_locations = [loc.strip().lower() for loc in (pref.locations or []) if loc.strip()]
        if target_locations:
            job_loc = (job.location or "").lower()
            matched_loc = any(
                target_loc in job_loc or job_loc in target_loc
                for target_loc in target_locations
            )
            if not matched_loc:
                return MatchResult(
                    passed=False,
                    score=0.0,
                    reasons=[],
                    rejected_because=f"Location '{job.location}' does not match target locations: {', '.join(pref.locations)}",
                )

    # 5. Salary
    has_salary = (job.salary_max is not None) or (job.salary_min is not None)
    salary_reason = None
    if pref.min_salary is not None:
        if has_salary:
            job_curr = (job.salary_currency or "").strip().upper()
            pref_curr = (pref.salary_currency or "").strip().upper()
            if job_curr and pref_curr and job_curr != pref_curr:
                return MatchResult(
                    passed=False,
                    score=0.0,
                    reasons=[],
                    rejected_because=f"Salary currency mismatch: job is {job_curr}, preference is {pref_curr}",
                )

            effective_salary = job.salary_max if job.salary_max is not None else job.salary_min
            if effective_salary is not None and effective_salary < pref.min_salary:
                return MatchResult(
                    passed=False,
                    score=0.0,
                    reasons=[],
                    rejected_because=f"Salary {effective_salary} {job_curr} is below minimum requirement {pref.min_salary} {pref_curr}",
                )

            if job.salary_min and job.salary_max:
                salary_reason = f"Salary {job.salary_min:,} - {job.salary_max:,} {job_curr} meets your minimum"
            else:
                salary_reason = f"Salary {effective_salary:,} {job_curr} meets your minimum"
        else:
            salary_reason = "Salary not listed"
    elif has_salary:
        curr = (job.salary_currency or "").upper()
        if job.salary_min and job.salary_max:
            salary_reason = f"Salary listed: {job.salary_min:,} - {job.salary_max:,} {curr}"
        else:
            eff = job.salary_max or job.salary_min
            salary_reason = f"Salary listed: {eff:,} {curr}"
    else:
        salary_reason = "Salary not listed"

    # 6. Title relevance
    target_titles = pref.target_titles or []
    title_sim, matched_target = _compute_title_similarity(job.title, target_titles)
    if target_titles and title_sim < 0.34:
        return MatchResult(
            passed=False,
            score=title_sim,
            reasons=[],
            rejected_because=f"Title similarity {title_sim:.2f} is below 0.34 threshold for target titles",
        )

    # Soft Scoring
    # Title similarity weight: 0.45
    title_contrib = title_sim * 0.45

    # Skills overlap weight: 0.30
    profile_skills = [s.strip().lower() for s in (profile.skills or []) if s.strip()]
    matched_skills = []
    desc_lower = (job.description or "").lower()
    for skill in profile_skills:
        if re.search(r"\b" + re.escape(skill) + r"\b", desc_lower):
            matched_skills.append(skill)

    skills_ratio = (len(matched_skills) / len(profile_skills)) if profile_skills else 0.5
    skills_contrib = skills_ratio * 0.30

    # Include keywords hit rate weight: 0.15
    include_kws = [k.strip().lower() for k in (pref.include_keywords or []) if k.strip()]
    matched_include = []
    for kw in include_kws:
        if re.search(r"\b" + re.escape(kw) + r"\b", job_text):
            matched_include.append(kw)

    include_ratio = (len(matched_include) / len(include_kws)) if include_kws else 1.0
    include_contrib = include_ratio * 0.15

    # Recency weight: 0.10 (posted in last 3 days = 1.0, decays to 0 at 30 days)
    now = datetime.now(timezone.utc)
    if job.posted_at:
        posted = job.posted_at
        if posted.tzinfo is None:
            posted = posted.replace(tzinfo=timezone.utc)
        days_old = max(0.0, (now - posted).total_seconds() / 86400.0)
        if days_old <= 3.0:
            recency_ratio = 1.0
        elif days_old >= 30.0:
            recency_ratio = 0.0
        else:
            recency_ratio = 1.0 - ((days_old - 3.0) / 27.0)
    else:
        recency_ratio = 0.5
    recency_contrib = recency_ratio * 0.10

    raw_score = title_contrib + skills_contrib + include_contrib + recency_contrib

    # Deductions
    if job_mode == "unknown":
        raw_score -= 0.05
    if not has_salary:
        raw_score -= 0.05

    final_score = max(0.0, min(1.0, round(raw_score, 4)))

    # Build human-readable reasons
    if matched_target:
        reasons.append(f"Title matches '{matched_target}'")
    if matched_skills:
        reasons.append(f"{len(matched_skills)} of your skills appear in the description")
    if job_mode == "remote":
        reasons.append("Remote")
    elif job_mode in ("hybrid", "onsite") and job.location:
        reasons.append(f"{job_mode.capitalize()} in {job.location}")
    if salary_reason:
        reasons.append(salary_reason)
    if matched_include:
        reasons.append(f"Keywords matched: {', '.join(matched_include)}")

    min_required = pref.min_match_score if pref.min_match_score is not None else 0.55
    if final_score < min_required:
        return MatchResult(
            passed=False,
            score=final_score,
            reasons=reasons,
            rejected_because=f"Match score {final_score:.2f} is below minimum {min_required:.2f}",
        )

    return MatchResult(
        passed=True,
        score=final_score,
        reasons=reasons,
        rejected_because=None,
    )
