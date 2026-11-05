from __future__ import annotations

import logging
from datetime import timedelta
from django.conf import settings
from django.utils import timezone
from agents.models import AgentAction

logger = logging.getLogger(__name__)

HARD_WEEKLY_APPLICATION_CEILING = 25

def is_screening_enabled() -> bool:
    return getattr(settings, 'SCREENING_AGENT_ENABLED', True)

def is_digest_enabled() -> bool:
    return getattr(settings, 'DIGEST_AGENT_ENABLED', True)

def is_auto_apply_enabled() -> bool:
    return getattr(settings, 'AUTO_APPLY_AGENT_ENABLED', True)

def is_scheduling_enabled() -> bool:
    return getattr(settings, 'SCHEDULING_AGENT_ENABLED', True)

def is_agent_enabled(agent_type: str) -> bool:
    mapping = {
        'screening': is_screening_enabled,
        'digest': is_digest_enabled,
        'auto_apply': is_auto_apply_enabled,
        'scheduling': is_scheduling_enabled,
    }
    checker = mapping.get(agent_type)
    return checker() if checker else True

def get_weekly_application_count(user_id: int) -> int:
    """
    Authoritative count directly from PostgreSQL as the single source of truth.
    Does not rely on volatile or potentially stale Redis cache.
    """
    week_ago = timezone.now() - timedelta(days=7)
    return AgentAction.objects.filter(
        agent_type='auto_apply',
        user_id=user_id,
        status__in=['approved', 'auto_executed'],
        created_at__gte=week_ago,
    ).count()

def get_cached_weekly_application_count(user_id: int) -> int:
    # Backwards-compatible alias for existing callers
    return get_weekly_application_count(user_id)


def check_weekly_cap_reached(user_id: int) -> bool:
    recent_count = get_cached_weekly_application_count(user_id)
    reached = recent_count >= HARD_WEEKLY_APPLICATION_CEILING
    if reached:
        try:
            from agents.metrics import track_guardrail_block
            track_guardrail_block("weekly_ceiling", "ceiling_exceeded")
        except Exception:
            pass
    return reached

def check_weekly_ceiling(user_or_id) -> bool:
    user_id = user_or_id.id if hasattr(user_or_id, 'id') else int(user_or_id)
    return not check_weekly_cap_reached(user_id)
