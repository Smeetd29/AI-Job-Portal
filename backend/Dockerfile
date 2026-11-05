# syntax=docker/dockerfile:1.4
# Multi-stage backend image with API and ML worker targets

# ----------------- Stage 1A: Base API Dependency Builder -----------------
FROM python:3.11-slim AS builder-api

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /install

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --prefix=/install/deps -r requirements.txt

# ----------------- Stage 1B: ML Dependency Builder (CPU-Only PyTorch) -----------------
FROM builder-api AS builder-ml

COPY requirements-ml.txt .
RUN pip install --prefix=/install/deps --index-url https://download.pytorch.org/whl/cpu --extra-index-url https://pypi.org/simple -r requirements-ml.txt

# ----------------- Stage 2: Common Runtime Base -----------------
FROM python:3.11-slim AS runtime-base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/install/deps/bin:$PATH" \
    PYTHONPATH="/install/deps/lib/python3.11/site-packages:$PYTHONPATH" \
    HF_HOME="/app/.cache/huggingface" \
    SENTENCE_TRANSFORMERS_HOME="/app/.cache/huggingface"

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd -g 10001 appgroup && \
    useradd -u 10001 -g appgroup -s /bin/bash -m appuser && \
    mkdir -p /app/staticfiles /app/media /app/data /app/.cache/huggingface && \
    chown -R appuser:appgroup /app

# ----------------- Stage 3: API Runtime (CPU ML Inference) -----------------
FROM runtime-base AS api

COPY --from=builder-ml /install/deps /install/deps
COPY --chown=appuser:appgroup . /app

USER appuser

ENV DJANGO_SETTINGS_MODULE="job.settings" \
    SECRET_KEY="docker-build-time-key-not-for-production" \
    DATABASE_URL="sqlite:////tmp/build.db" \
    USE_REDIS_CACHE="False"

RUN python scripts/preload_models.py || true
RUN python manage.py collectstatic --noinput && rm -f /tmp/build.db

EXPOSE 8000
STOPSIGNAL SIGTERM

HEALTHCHECK --interval=20s --timeout=5s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

CMD ["gunicorn", "job.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--threads", "2", "--timeout", "60", "--access-logfile", "-", "--error-logfile", "-"]

# ----------------- Stage 4: ML Worker Runtime (CPU PyTorch + Preloaded Weights) -----------------
FROM runtime-base AS worker

COPY --from=builder-ml /install/deps /install/deps
COPY --chown=appuser:appgroup . /app

USER appuser
RUN python scripts/preload_models.py || true

STOPSIGNAL SIGTERM

CMD ["celery", "-A", "job.celery", "app", "worker", "-l", "info", "--concurrency=2"]

# Default target for standard builds
FROM api AS final
