from __future__ import annotations

import logging
from prometheus_client import Counter, Histogram

logger = logging.getLogger(__name__)

# Agent Execution Metrics
AGENT_RUNS_TOTAL = Counter(
    "careerconnect_agent_runs_total",
    "Total number of agent runs executed",
    ["agent_type", "trigger", "status"],
)

AGENT_ACTIONS_TOTAL = Counter(
    "careerconnect_agent_actions_total",
    "Total number of agent actions generated or transitioned",
    ["agent_type", "action_type", "status"],
)

GUARDRAIL_BLOCKS_TOTAL = Counter(
    "careerconnect_guardrail_blocks_total",
    "Total count of actions blocked by guardrails",
    ["guardrail_name", "reason"],
)

LLM_REQUEST_DURATION_SECONDS = Histogram(
    "careerconnect_llm_request_duration_seconds",
    "Duration of LLM calls in seconds",
    ["model"],
    buckets=(0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
)

EMAILS_SENT_TOTAL = Counter(
    "careerconnect_emails_sent_total",
    "Total count of transactional emails dispatched",
    ["email_type", "status"],
)

def track_agent_run(agent_type: str, trigger: str, status: str) -> None:
    try:
        AGENT_RUNS_TOTAL.labels(agent_type=agent_type, trigger=trigger, status=status).inc()
    except Exception as exc:
        logger.debug("Metrics collection skipped: %s", exc)

def track_agent_action(agent_type: str, action_type: str, status: str) -> None:
    try:
        AGENT_ACTIONS_TOTAL.labels(agent_type=agent_type, action_type=action_type, status=status).inc()
    except Exception as exc:
        logger.debug("Metrics collection skipped: %s", exc)

def track_guardrail_block(guardrail_name: str, reason: str = "cap_exceeded") -> None:
    try:
        GUARDRAIL_BLOCKS_TOTAL.labels(guardrail_name=guardrail_name, reason=reason).inc()
    except Exception as exc:
        logger.debug("Metrics collection skipped: %s", exc)

def track_email_sent(email_type: str, status: str = "success") -> None:
    try:
        EMAILS_SENT_TOTAL.labels(email_type=email_type, status=status).inc()
    except Exception as exc:
        logger.debug("Metrics collection skipped: %s", exc)
