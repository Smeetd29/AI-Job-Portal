import importlib
import logging
from typing import Protocol, runtime_checkable
from django.conf import settings
from ..models import QueueItem

logger = logging.getLogger(__name__)


@runtime_checkable
class Applier(Protocol):
    def apply(self, item: QueueItem) -> dict:
        """Apply for a job on behalf of the candidate."""
        ...


class LinkApplier:
    """
    v1 Safe Applier: Marks the queue item as APPLIED, records apply_url and cover note,
    enabling the candidate/frontend to complete submission directly on the target portal.
    """
    def apply(self, item: QueueItem) -> dict:
        result = {
            "method": "link",
            "apply_url": item.job.apply_url,
            "cover_note": item.cover_note,
        }
        item.status = "APPLIED"
        item.apply_result = result
        item.save(update_fields=["status", "apply_result", "updated_at"])
        return result


def get_applier() -> Applier:
    """Factory loading configured Applier backend."""
    backend = getattr(settings, "APPLIER_BACKEND", "link")
    if backend == "link":
        return LinkApplier()

    try:
        module_path, class_name = backend.rsplit(".", 1)
        module = importlib.import_module(module_path)
        cls = getattr(module, class_name)
        return cls()
    except Exception as exc:
        logger.warning(f"Could not load custom APPLIER_BACKEND '{backend}', falling back to LinkApplier: {exc}")
        return LinkApplier()


def apply(item: QueueItem) -> dict:
    """
    Executes the apply action for an approved QueueItem.
    On failure, marks status as FAILED and saves the error payload.
    """
    try:
        applier = get_applier()
        return applier.apply(item)
    except Exception as exc:
        logger.error(f"Applier failed for QueueItem {item.id}: {exc}")
        item.status = "FAILED"
        item.apply_result = {"error": str(exc)}
        item.save(update_fields=["status", "apply_result", "updated_at"])
        raise
