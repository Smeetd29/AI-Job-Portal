from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from copilot.models import CandidateProfile, JobPreference

User = get_user_model()


class Command(BaseCommand):
    help = "Seeds demo candidate user, realistic resume profile, and preferences."

    def handle(self, *args, **options):
        email = "demo@example.com"
        username = "demo@example.com"

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": "Siddharth",
                "last_name": "Mehta",
                "is_staff": True,
            },
        )
        user.set_password("DemoPassword123!")
        user.save()

        if created:
            self.stdout.write(self.style.SUCCESS(f"Created user {username}"))
        else:
            self.stdout.write(self.style.WARNING(f"User {username} already exists, updating profile..."))

        resume_text = (
            "Siddharth Mehta\n"
            "Senior Backend Engineer - Mumbai, India | demo@example.com\n\n"
            "SUMMARY:\n"
            "Senior backend engineer with 6+ years of experience specializing in Python, Django, PostgreSQL, "
            "and distributed task queues.\n\n"
            "EXPERIENCE:\n"
            "ScaleTech Solutions - Senior Backend Engineer (2021 - Present)\n"
            "- Designed Celery and Redis asynchronous task pipelines processing 2M+ background tasks daily.\n"
            "- Optimized PostgreSQL queries and database schemas, reducing p95 API response times by 80%.\n"
            "- Built Docker-based CI/CD workflows on AWS.\n\n"
            "InnoByte Labs - Software Engineer (2018 - 2021)\n"
            "- Developed high-throughput REST APIs using Django REST Framework.\n"
            "- Architected session and token authentication services for 200,000+ active users.\n\n"
            "EDUCATION:\n"
            "B.Tech in Computer Science, Mumbai University (2014 - 2018)\n\n"
            "SKILLS:\n"
            "Python, Django, FastAPI, PostgreSQL, Celery, Redis, Docker, AWS, REST APIs"
        )

        profile, _ = CandidateProfile.objects.update_or_create(
            user=user,
            defaults={
                "full_name": "Siddharth Mehta",
                "headline": "Senior Backend Engineer | Python, Django, PostgreSQL, Distributed Systems",
                "summary": "Senior backend engineer with 6+ years building high-throughput APIs, background workers, and cloud architectures.",
                "skills": ["Python", "Django", "FastAPI", "PostgreSQL", "Celery", "Redis", "Docker", "AWS", "REST APIs"],
                "experience": [
                    {
                        "company": "ScaleTech Solutions",
                        "title": "Senior Backend Engineer",
                        "start": "2021-06",
                        "end": "Present",
                        "highlights": [
                            "Designed Celery and Redis asynchronous pipelines processing 2M+ background tasks daily.",
                            "Optimized PostgreSQL schema and indexing, cutting 95th percentile response times.",
                        ],
                    },
                    {
                        "company": "InnoByte Labs",
                        "title": "Software Engineer",
                        "start": "2018-08",
                        "end": "2021-05",
                        "highlights": [
                            "Implemented core REST APIs using Django and Django REST Framework.",
                            "Built authentication and RBAC services for 200k+ active users.",
                        ],
                    },
                ],
                "resume_text": resume_text,
            },
        )

        JobPreference.objects.update_or_create(
            candidate=profile,
            defaults={
                "target_titles": ["Backend Engineer", "Python Developer"],
                "min_salary": 1800000,
                "salary_currency": "INR",
                "work_modes": ["remote", "hybrid"],
                "locations": ["Mumbai"],
                "include_keywords": ["Django", "PostgreSQL", "Celery"],
                "exclude_keywords": ["Crypto", "PHP"],
                "exclude_companies": ["BadCompany Inc"],
                "max_queue_per_day": 10,
                "min_match_score": 0.55,
                "agent_enabled": True,
            },
        )

        self.stdout.write(self.style.SUCCESS("Successfully seeded demo candidate profile and preferences!"))
        self.stdout.write(self.style.SUCCESS("Login credentials: demo@example.com / DemoPassword123!"))
