import pytest
from datetime import datetime, timezone, timedelta
from copilot.services.matching import evaluate
from copilot.sources.base import JobDTO
from .factories import CandidateProfileFactory, JobPreferenceFactory


@pytest.fixture
def base_profile_and_pref(db):
    profile = CandidateProfileFactory(
        skills=["Python", "Django", "PostgreSQL", "Celery", "Redis"],
    )
    pref = JobPreferenceFactory(
        candidate=profile,
        target_titles=["Backend Engineer", "Python Developer"],
        min_salary=1800000,
        salary_currency="INR",
        work_modes=["remote", "hybrid"],
        locations=["Mumbai"],
        include_keywords=["Django", "PostgreSQL"],
        exclude_keywords=["Crypto", "PHP"],
        exclude_companies=["SpamCorp"],
        min_match_score=0.50,
    )
    return profile, pref


def test_company_exclusion(base_profile_and_pref):
    profile, pref = base_profile_and_pref
    job = JobDTO(
        source="mock",
        external_id="1",
        title="Backend Engineer",
        company="SpamCorp",
        location="Remote",
        work_mode="remote",
        description="Great Python role",
        apply_url="https://example.com/1",
    )
    res = evaluate(job, pref, profile)
    assert not res.passed
    assert "SpamCorp" in (res.rejected_because or "")


def test_exclude_keywords_in_title(base_profile_and_pref):
    profile, pref = base_profile_and_pref
    job = JobDTO(
        source="mock",
        external_id="2",
        title="Crypto Backend Engineer",
        company="Future Finance",
        location="Remote",
        work_mode="remote",
        description="Python backend development",
        apply_url="https://example.com/2",
    )
    res = evaluate(job, pref, profile)
    assert not res.passed
    assert "excluded keyword 'crypto'" in (res.rejected_because or "").lower()


def test_exclude_keywords_in_description(base_profile_and_pref):
    profile, pref = base_profile_and_pref
    job = JobDTO(
        source="mock",
        external_id="3",
        title="Backend Engineer",
        company="Legacy Tech",
        location="Remote",
        work_mode="remote",
        description="We are migrating our legacy PHP code to modern systems.",
        apply_url="https://example.com/3",
    )
    res = evaluate(job, pref, profile)
    assert not res.passed
    assert "excluded keyword 'php'" in (res.rejected_because or "").lower()


def test_work_mode_filter(base_profile_and_pref):
    profile, pref = base_profile_and_pref
    # Onsite is not in pref.work_modes (remote, hybrid)
    job = JobDTO(
        source="mock",
        external_id="4",
        title="Backend Engineer",
        company="Corp",
        location="Mumbai",
        work_mode="onsite",
        description="Python Django role",
        apply_url="https://example.com/4",
    )
    res = evaluate(job, pref, profile)
    assert not res.passed
    assert "Work mode 'onsite' not in target modes" in (res.rejected_because or "")


def test_location_filter_for_hybrid(base_profile_and_pref):
    profile, pref = base_profile_and_pref
    # Pref location is Mumbai; job is Delhi
    job = JobDTO(
        source="mock",
        external_id="5",
        title="Backend Engineer",
        company="Corp",
        location="Delhi, India",
        work_mode="hybrid",
        description="Python Django role",
        apply_url="https://example.com/5",
    )
    res = evaluate(job, pref, profile)
    assert not res.passed
    assert "does not match target locations" in (res.rejected_because or "")

    # Job is Mumbai -> passes location check
    job_mumbai = JobDTO(
        source="mock",
        external_id="5b",
        title="Backend Engineer",
        company="Corp",
        location="Mumbai, MH",
        work_mode="hybrid",
        description="Python Django PostgreSQL backend role",
        apply_url="https://example.com/5b",
        salary_min=2000000,
        salary_currency="INR",
        posted_at=datetime.now(timezone.utc),
    )
    res_mumbai = evaluate(job_mumbai, pref, profile)
    assert res_mumbai.passed


def test_salary_currency_mismatch(base_profile_and_pref):
    profile, pref = base_profile_and_pref
    job = JobDTO(
        source="mock",
        external_id="6",
        title="Backend Engineer",
        company="GlobalTech",
        location="Remote",
        work_mode="remote",
        description="Python Django role",
        apply_url="https://example.com/6",
        salary_min=100000,
        salary_max=120000,
        salary_currency="USD",
    )
    res = evaluate(job, pref, profile)
    assert not res.passed
    assert "currency mismatch" in (res.rejected_because or "").lower()


def test_salary_below_minimum(base_profile_and_pref):
    profile, pref = base_profile_and_pref
    job = JobDTO(
        source="mock",
        external_id="7",
        title="Backend Engineer",
        company="StartUp",
        location="Remote",
        work_mode="remote",
        description="Python Django role",
        apply_url="https://example.com/7",
        salary_min=1200000,
        salary_max=1500000,
        salary_currency="INR",
    )
    res = evaluate(job, pref, profile)
    assert not res.passed
    assert "below minimum requirement" in (res.rejected_because or "").lower()


def test_missing_salary_passes_with_penalty(base_profile_and_pref):
    profile, pref = base_profile_and_pref
    job = JobDTO(
        source="mock",
        external_id="8",
        title="Backend Engineer",
        company="Stealth AI",
        location="Remote",
        work_mode="remote",
        description="Python Django PostgreSQL Celery Redis engineer",
        apply_url="https://example.com/8",
        salary_min=None,
        salary_max=None,
        salary_currency="",
        posted_at=datetime.now(timezone.utc),
    )
    res = evaluate(job, pref, profile)
    assert res.passed
    assert "Salary not listed" in res.reasons


def test_title_relevance_threshold(base_profile_and_pref):
    profile, pref = base_profile_and_pref
    job = JobDTO(
        source="mock",
        external_id="9",
        title="Graphic Designer & UI Illustrator",
        company="Creative Agency",
        location="Remote",
        work_mode="remote",
        description="Create illustrations and logos with Figma and Photoshop.",
        apply_url="https://example.com/9",
    )
    res = evaluate(job, pref, profile)
    assert not res.passed
    assert "below 0.34 threshold" in (res.rejected_because or "")


def test_scoring_bounds_and_skills_keywords_overlap(base_profile_and_pref):
    profile, pref = base_profile_and_pref
    # High match job
    job_high = JobDTO(
        source="mock",
        external_id="10",
        title="Senior Python Backend Engineer",
        company="Peak Tech",
        location="Remote",
        work_mode="remote",
        description=(
            "Looking for an experienced engineer in Python, Django, PostgreSQL, "
            "Celery, and Redis. Docker experience preferred."
        ),
        apply_url="https://example.com/10",
        salary_min=2200000,
        salary_max=2800000,
        salary_currency="INR",
        posted_at=datetime.now(timezone.utc) - timedelta(hours=5),
    )
    res_high = evaluate(job_high, pref, profile)
    assert res_high.passed
    assert 0.0 <= res_high.score <= 1.0
    assert res_high.score >= 0.70
    assert any("skills appear in the description" in r for r in res_high.reasons)
    assert any("meets your minimum" in r for r in res_high.reasons)
