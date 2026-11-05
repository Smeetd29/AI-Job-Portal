from __future__ import annotations

import contextvars
import time
import uuid
import logging
from typing import Optional

logger = logging.getLogger("access")

_request_id_ctx: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar("request_id", default=None)

def get_current_request_id() -> Optional[str]:
    return _request_id_ctx.get()

class RequestIDMiddleware:
    """Extracts or generates an X-Request-ID and attaches it to request, response, and logging context."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        request.request_id = req_id
        token = _request_id_ctx.set(req_id)

        start_time = time.perf_counter()
        response = self.get_response(request)
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)

        response["X-Request-ID"] = req_id

        # Skip spamming logs on health probes
        if request.path not in ("/healthz", "/readyz", "/metrics"):
            user_id = getattr(getattr(request, "user", None), "id", None)
            logger.info(
                "%s %s %s (%sms)",
                request.method,
                request.path,
                response.status_code,
                duration_ms,
                extra={
                    "path": request.path,
                    "method": request.method,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "user_id": user_id,
                    "request_id": req_id,
                },
            )

        _request_id_ctx.reset(token)
        return response

class SecurityHeadersMiddleware:
    """Adds Content-Security-Policy and Permissions-Policy headers to responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data: https: blob:; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "
            "connect-src 'self' https: wss:;"
        )
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        return response
