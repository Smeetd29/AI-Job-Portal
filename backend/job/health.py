from __future__ import annotations

import logging
import time
from django.db import connection
from django.core.cache import cache
from django.http import JsonResponse
from rest_framework.permissions import AllowAny
from rest_framework.decorators import api_view, permission_classes

logger = logging.getLogger(__name__)

@api_view(['GET'])
@permission_classes([AllowAny])
def healthz(request):
    """Liveness probe: verifies process is alive and responsive."""
    return JsonResponse({"status": "healthy", "service": "careerconnect-backend"}, status=200)

@api_view(['GET'])
@permission_classes([AllowAny])
def readyz(request):
    """Readiness probe: checks PostgreSQL connection and Redis cache connectivity."""
    checks = {
        "database": False,
        "redis": False,
        "database_latency_ms": None,
        "redis_latency_ms": None,
    }
    status_code = 200

    # 1. Database check
    db_start = time.perf_counter()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            row = cursor.fetchone()
            if row and row[0] == 1:
                checks["database"] = True
                checks["database_latency_ms"] = round((time.perf_counter() - db_start) * 1000, 2)
    except Exception as exc:
        logger.error("Health check database failure: %s", exc)
        checks["database_error"] = str(exc)
        status_code = 503

    # 2. Redis Cache check (graceful fallback: reports degraded rather than 503 if cache misses are acceptable)
    redis_start = time.perf_counter()
    try:
        test_key = "health:ping"
        cache.set(test_key, "pong", timeout=10)
        val = cache.get(test_key)
        if val == "pong":
            checks["redis"] = True
            checks["redis_latency_ms"] = round((time.perf_counter() - redis_start) * 1000, 2)
        else:
            checks["redis"] = False
            checks["redis_status"] = "cache_miss_fallback"
    except Exception as exc:
        logger.warning("Health check redis degraded: %s", exc)
        checks["redis"] = False
        checks["redis_status"] = "degraded_fallback"

    overall_status = "ready" if checks["database"] else "unready"
    return JsonResponse(
        {
            "status": overall_status,
            "checks": checks,
        },
        status=status_code,
    )
