import os
import sys
from pathlib import Path
from celery.schedules import crontab
import dj_database_url

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-career-copilot-dev-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "1").lower() in ("1", "true", "yes")

allowed_hosts_str = os.environ.get("DJANGO_ALLOWED_HOSTS", "*")
ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_str.split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_celery_beat",
    "copilot.apps.CopilotConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database
DATABASE_URL = os.environ.get("DATABASE_URL")
IS_TESTING = "pytest" in sys.modules or any("test" in arg for arg in sys.argv)

if DATABASE_URL and not (IS_TESTING and "postgres" in DATABASE_URL and "test" not in DATABASE_URL):
    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
        )
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# Redis & Celery
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TIMEZONE = "UTC"
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

DAILY_RUN_HOUR_UTC = int(os.environ.get("DAILY_RUN_HOUR_UTC", "3"))

CELERY_BEAT_SCHEDULE = {
    "daily-career-copilot-run": {
        "task": "copilot.tasks.run_daily_for_all_candidates",
        "schedule": crontab(hour=DAILY_RUN_HOUR_UTC, minute=0),
    },
    "expire-stale-queue-items": {
        "task": "copilot.tasks.expire_stale_queue_items",
        "schedule": crontab(hour=4, minute=0),
    },
}

CELERY_TASK_ALWAYS_EAGER = (
    os.environ.get("CELERY_TASK_ALWAYS_EAGER", "0").lower() in ("1", "true", "yes")
    or IS_TESTING
)
if CELERY_TASK_ALWAYS_EAGER:
    CELERY_TASK_EAGER_PROPAGATES = True

# App Specific Configurations
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5-5")

raw_sources = os.environ.get("ENABLED_JOB_SOURCES", "remotive,mock")
ENABLED_JOB_SOURCES = [s.strip() for s in raw_sources.split(",") if s.strip()]

DEFAULT_MAX_QUEUE_PER_DAY = int(os.environ.get("DEFAULT_MAX_QUEUE_PER_DAY", "10"))
QUEUE_ITEM_TTL_DAYS = int(os.environ.get("QUEUE_ITEM_TTL_DAYS", "7"))
APPLIER_BACKEND = os.environ.get("APPLIER_BACKEND", "link")
