from datetime import datetime, timezone, timedelta
from typing import List, Optional
from .base import JobDTO, JobSource


class MockJobSource(JobSource):
    name = "mock"

    def fetch(self, *, titles: List[str], since: Optional[datetime] = None) -> List[JobDTO]:
        now = datetime.now(timezone.utc)
        jobs = [
            JobDTO(
                source="mock",
                external_id="mock-101",
                title="Senior Backend Engineer",
                company="Acme Tech",
                location="Remote",
                work_mode="remote",
                description=(
                    "We are looking for a Senior Backend Engineer proficient in Python, Django, "
                    "PostgreSQL, Celery, and Redis. You will build high-throughput microservices, "
                    "design distributed task workflows, and optimize database queries."
                ),
                apply_url="https://example.com/jobs/mock-101",
                posted_at=now - timedelta(days=1),
                salary_min=2000000,
                salary_max=2600000,
                salary_currency="INR",
                raw={"id": "mock-101", "mock": True},
            ),
            JobDTO(
                source="mock",
                external_id="mock-102",
                title="Python Developer",
                company="CloudScale Solutions",
                location="Mumbai, India",
                work_mode="hybrid",
                description=(
                    "Seeking a talented Python Developer to join our team in Mumbai. "
                    "Experience with Python, Django, REST APIs, Docker, and PostgreSQL required. "
                    "Collaborate with product teams to ship mission-critical features."
                ),
                apply_url="https://example.com/jobs/mock-102",
                posted_at=now - timedelta(days=2),
                salary_min=1800000,
                salary_max=2200000,
                salary_currency="INR",
                raw={"id": "mock-102", "mock": True},
            ),
            JobDTO(
                source="mock",
                external_id="mock-103",
                title="Backend Engineer",
                company="DataForge Analytics",
                location="Remote",
                work_mode="remote",
                description=(
                    "DataForge is hiring a Backend Engineer to scale data pipelines and API services. "
                    "Core stack: Python, Django, Redis, PostgreSQL. Great remote work culture."
                ),
                apply_url="https://example.com/jobs/mock-103",
                posted_at=now - timedelta(days=3),
                salary_min=None,
                salary_max=None,
                salary_currency="",
                raw={"id": "mock-103", "mock": True},
            ),
            JobDTO(
                source="mock",
                external_id="mock-104",
                title="Frontend Specialist",
                company="UIWorld",
                location="Remote",
                work_mode="remote",
                description=(
                    "Looking for a Frontend Specialist skilled in React, TypeScript, and modern CSS. "
                    "Design and implement responsive interfaces for enterprise customers."
                ),
                apply_url="https://example.com/jobs/mock-104",
                posted_at=now - timedelta(days=4),
                salary_min=1200000,
                salary_max=1600000,
                salary_currency="INR",
                raw={"id": "mock-104", "mock": True},
            ),
            JobDTO(
                source="mock",
                external_id="mock-105",
                title="Staff Software Engineer",
                company="BadCompany Inc",
                location="Bangalore, India",
                work_mode="onsite",
                description=(
                    "Staff Software Engineer needed for legacy enterprise monolith. "
                    "Onsite only in Bangalore. Java and C++."
                ),
                apply_url="https://example.com/jobs/mock-105",
                posted_at=now - timedelta(days=5),
                salary_min=3000000,
                salary_max=4000000,
                salary_currency="INR",
                raw={"id": "mock-105", "mock": True},
            ),
        ]

        if since:
            jobs = [j for j in jobs if j.posted_at and j.posted_at >= since]

        return jobs
