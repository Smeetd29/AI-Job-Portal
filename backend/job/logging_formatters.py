from __future__ import annotations

import json
import logging
import traceback
from datetime import datetime, timezone
from job.middleware import get_current_request_id

class JSONFormatter(logging.Formatter):
    """Formats log records as single-line JSON objects with request correlation IDs."""

    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": getattr(record, "request_id", None) or get_current_request_id(),
        }

        # Include exception traceback if present
        if record.exc_info:
            log_data["exception"] = "".join(traceback.format_exception(*record.exc_info))

        # Include extra attributes
        for key in ("path", "method", "status_code", "duration_ms", "user_id"):
            if hasattr(record, key):
                log_data[key] = getattr(record, key)

        return json.dumps(log_data)
