from dataclasses import dataclass
from datetime import datetime
from abc import ABC, abstractmethod


@dataclass
class JobDTO:
    source: str
    external_id: str
    title: str
    company: str
    location: str
    work_mode: str  # remote|hybrid|onsite|unknown
    description: str
    apply_url: str
    posted_at: datetime | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str = ""
    raw: dict | None = None


class JobSource(ABC):
    name: str

    @abstractmethod
    def fetch(self, *, titles: list[str], since: datetime | None = None) -> list[JobDTO]:
        """Fetch jobs matching titles posted since given timestamp."""
        pass
