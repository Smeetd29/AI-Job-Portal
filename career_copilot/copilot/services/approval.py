import logging
from typing import Optional
from django.db import transaction
from django.utils import timezone
from ..models import QueueItem

logger = logging.getLogger(__name__)


class InvalidTransition(Exception):
    """Raised when an invalid status transition is attempted on a QueueItem."""
    pass


def approve(item: QueueItem, *, edited_note: Optional[str] = None) -> QueueItem:
    """
    Candidate single-tap approval for a pending job application.
    Enforces atomic status transition with select_for_update to prevent double-tap race conditions.
    Dispatches apply_item_task.
    """
    with transaction.atomic():
        locked = (
            QueueItem.objects.select_for_update()
            .select_related("job", "candidate")
            .get(id=item.id)
        )
        if locked.status != "PENDING":
            raise InvalidTransition(f"Item {item.id} is in status '{locked.status}', expected 'PENDING'.")

        if edited_note is not None:
            locked.cover_note = edited_note

        locked.status = "APPROVED"
        locked.decided_at = timezone.now()
        locked.save()

    # Trigger apply action via Celery task
    from ..tasks import apply_item_task
    apply_item_task.delay(str(locked.id))

    locked.refresh_from_db()
    return locked


def reject(item: QueueItem) -> QueueItem:
    """
    Rejects a pending queue item.
    """
    with transaction.atomic():
        locked = (
            QueueItem.objects.select_for_update()
            .select_related("job", "candidate")
            .get(id=item.id)
        )
        if locked.status != "PENDING":
            raise InvalidTransition(f"Item {item.id} is in status '{locked.status}', expected 'PENDING'.")

        locked.status = "REJECTED"
        locked.decided_at = timezone.now()
        locked.save()

    return locked


def expire_stale() -> int:
    """
    Flips PENDING items past their expiration datetime to EXPIRED.
    Returns count of updated items.
    """
    now = timezone.now()
    count = QueueItem.objects.filter(
        status="PENDING",
        expires_at__lt=now,
    ).update(
        status="EXPIRED",
        updated_at=now,
    )
    return count
