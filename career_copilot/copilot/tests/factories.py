from datetime import datetime, timezone, timedelta
import factory
from django.contrib.auth import get_user_model
from ..models import CandidateProfile, JobPreference, Job, QueueItem, AgentRun

User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    first_name = "Alex"
    last_name = "Candidate"


class CandidateProfileFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = CandidateProfile

    user = factory.SubFactory(UserFactory)
    full_name = "Alex Candidate"
    headline = "Senior Backend Engineer | Python & Django"
    summary = "Experienced backend engineer building scalable distributed systems."
    skills = ["Python", "Django", "PostgreSQL", "Celery", "Redis", "Docker"]
    experience = [
        {
            "company": "TechCorp",
            "title": "Backend Engineer",
            "start": "2021",
            "end": "Present",
            "highlights": ["Designed asynchronous task architecture", "Optimized SQL queries by 40%"],
        }
    ]
    resume_text = (
        "Alex Candidate\n"
        "Senior Backend Engineer with 5 years experience in Python, Django, PostgreSQL, Celery, and Redis.\n"
        "TechCorp (2021 - Present): Built high-concurrency APIs, reduced query times by 40%.\n"
        "Education: B.Tech in Computer Science."
    )


class JobPreferenceFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = JobPreference

    candidate = factory.SubFactory(CandidateProfileFactory)
    target_titles = ["Backend Engineer", "Python Developer"]
    min_salary = 1800000
    salary_currency = "INR"
    work_modes = ["remote", "hybrid"]
    locations = ["Mumbai", "Remote"]
    include_keywords = ["Django", "PostgreSQL"]
    exclude_keywords = ["Crypto", "PHP"]
    exclude_companies = ["SpamCorp"]
    max_queue_per_day = 10
    min_match_score = 0.55
    agent_enabled = True


class JobFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Job

    source = "mock"
    external_id = factory.Sequence(lambda n: f"job_{n}")
    title = "Senior Backend Engineer"
    company = "GreatTech Inc"
    location = "Remote"
    work_mode = "remote"
    salary_min = 2000000
    salary_max = 2500000
    salary_currency = "INR"
    description = (
        "We need a Senior Backend Engineer proficient in Python, Django, PostgreSQL, and Celery. "
        "Build reliable distributed backend services."
    )
    apply_url = factory.Sequence(lambda n: f"https://example.com/apply/{n}")
    posted_at = factory.LazyFunction(lambda: datetime.now(timezone.utc) - timedelta(days=1))
    raw = {}


class QueueItemFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = QueueItem

    candidate = factory.SubFactory(CandidateProfileFactory)
    job = factory.SubFactory(JobFactory)
    match_score = 0.85
    match_reasons = ["Title matches 'Backend Engineer'", "Remote", "Salary meets minimum"]
    cover_note = "Dear Hiring Team, I am eager to apply for this backend position..."
    cover_note_model = "claude-sonnet-5-5"
    status = "PENDING"
    expires_at = factory.LazyFunction(lambda: datetime.now(timezone.utc) + timedelta(days=7))
    apply_result = {}


class AgentRunFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = AgentRun

    candidate = factory.SubFactory(CandidateProfileFactory)
    jobs_fetched = 5
    jobs_matched = 3
    items_queued = 2
    status = "OK"
    error = ""
