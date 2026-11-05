from typing import Dict, List, Type
from django.conf import settings
from .base import JobDTO, JobSource
from .mock import MockJobSource
from .remotive import RemotiveJobSource

SOURCE_REGISTRY: Dict[str, Type[JobSource]] = {
    "mock": MockJobSource,
    "remotive": RemotiveJobSource,
}


def get_enabled_sources() -> List[JobSource]:
    """Return instantiated job sources configured in ENABLED_JOB_SOURCES setting."""
    enabled_names = getattr(settings, "ENABLED_JOB_SOURCES", ["remotive", "mock"])
    sources: List[JobSource] = []
    for name in enabled_names:
        clean_name = name.strip().lower()
        if clean_name in SOURCE_REGISTRY:
            sources.append(SOURCE_REGISTRY[clean_name]())
    return sources


__all__ = ["JobDTO", "JobSource", "MockJobSource", "RemotiveJobSource", "get_enabled_sources"]
