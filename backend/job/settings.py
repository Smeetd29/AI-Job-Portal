
from pathlib import Path
from dotenv import load_dotenv
import os
import sys
from django.core.exceptions import ImproperlyConfigured

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

IS_RUNNING_TESTS = any('test' in arg or 'pytest' in arg for arg in sys.argv)
DEBUG = os.getenv('DEBUG', 'True').lower() in ('true', '1', 't')
PILOT_INVITE_ONLY = os.getenv('PILOT_INVITE_ONLY', 'False').lower() in ('true', '1', 't')
PILOT_INVITED_EMAILS = frozenset(
    email.strip().casefold()
    for email in os.getenv('PILOT_INVITED_EMAILS', '').split(',')
    if email.strip()
)

if PILOT_INVITE_ONLY and not PILOT_INVITED_EMAILS:
    raise ImproperlyConfigured(
        "PILOT_INVITE_ONLY requires at least one address in PILOT_INVITED_EMAILS."
    )

# When DEBUG is False (Production Mode), enforce strict secret key and host validation
raw_secret_key = os.getenv('SECRET_KEY')
if not DEBUG and not IS_RUNNING_TESTS:
    if (
        not raw_secret_key
        or raw_secret_key.startswith('django-insecure-')
        or 'change_me' in raw_secret_key.casefold()
        or 'placeholder' in raw_secret_key.casefold()
        or len(raw_secret_key) < 50
    ):
        raise ImproperlyConfigured(
            "Production deployment requires a secure, non-default SECRET_KEY environment variable "
            "with at least 50 characters."
        )
    SECRET_KEY = raw_secret_key
else:
    # Development and test runner fallback only
    SECRET_KEY = raw_secret_key or 'django-insecure-^8j1aw96@#zp9=1%2-ca=lm6w&r!1^317b+&uzberx64o6h#%s'

allowed_hosts_raw = os.getenv('ALLOWED_HOSTS', 'localhost,127.0.0.1,testserver')
ALLOWED_HOSTS = [h.strip() for h in allowed_hosts_raw.split(',') if h.strip()]

if not DEBUG and not IS_RUNNING_TESTS:
    if not os.getenv('ALLOWED_HOSTS') or not ALLOWED_HOSTS or '*' in ALLOWED_HOSTS:
        raise ImproperlyConfigured(
            "Production deployment requires explicitly configured ALLOWED_HOSTS without wildcard '*'."
        )

INSTALLED_APPS = [
    'django_prometheus',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'rest_framework',
    'corsheaders',
    'users',
    'jobs',
    'application',
    'agents',
]
AUTH_USER_MODEL = 'users.User'

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'job.middleware.RequestIDMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'job.middleware.SecurityHeadersMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = 'job.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

import dj_database_url
import sys

WSGI_APPLICATION = 'job.wsgi.application'

DATABASE_URL = os.getenv('DATABASE_URL')
CONN_MAX_AGE = int(os.getenv('CONN_MAX_AGE', '600'))

if DATABASE_URL:
    db_config = dj_database_url.parse(
        DATABASE_URL,
        conn_max_age=CONN_MAX_AGE,
        ssl_require=os.getenv('DB_SSL_REQUIRE', 'False').lower() in ('true', '1', 't'),
    )
    # Enable psycopg 3 connection pooling when PostgreSQL backend is used
    if 'postgresql' in db_config.get('ENGINE', '') and os.getenv('USE_DB_POOL', 'True').lower() in ('true', '1', 't'):
        db_config['CONN_MAX_AGE'] = 0
        db_config.setdefault('OPTIONS', {})['pool'] = {
            'min_size': int(os.getenv('DB_POOL_MIN_SIZE', '2')),
            'max_size': int(os.getenv('DB_POOL_MAX_SIZE', '10')),
            'timeout': float(os.getenv('DB_POOL_TIMEOUT', '10.0')),
        }
    DATABASES = {'default': db_config}
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

USE_S3_STORAGE = os.getenv('USE_S3_STORAGE', 'False').lower() in ('true', '1', 't')
AWS_QUERYSTRING_EXPIRE = int(os.getenv("AWS_QUERYSTRING_EXPIRE", "300"))

if not DEBUG and not IS_RUNNING_TESTS and USE_S3_STORAGE:
    storage_credentials = (
        os.getenv("AWS_ACCESS_KEY_ID", ""),
        os.getenv("AWS_SECRET_ACCESS_KEY", ""),
    )
    if any(
        not credential
        or credential.casefold() == "minioadmin"
        or "change_me" in credential.casefold()
        or "placeholder" in credential.casefold()
        for credential in storage_credentials
    ):
        raise ImproperlyConfigured(
            "Production object storage requires non-placeholder AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY values."
        )
    if not 1 <= AWS_QUERYSTRING_EXPIRE <= 300:
        raise ImproperlyConfigured(
            "Production presigned URL lifetime must be between 1 and 300 seconds."
        )

if USE_S3_STORAGE:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3.S3Storage",
            "OPTIONS": {
                "access_key": os.getenv("AWS_ACCESS_KEY_ID", "minioadmin"),
                "secret_key": os.getenv("AWS_SECRET_ACCESS_KEY", "minioadmin"),
                "bucket_name": os.getenv("AWS_STORAGE_BUCKET_NAME", "careerconnect-media"),
                "endpoint_url": os.getenv("AWS_S3_ENDPOINT_URL", "http://minio:9000"),
                "region_name": os.getenv("AWS_S3_REGION_NAME", "us-east-1"),
                "file_overwrite": False,
                "default_acl": None,
                "signature_version": "s3v4",
                "addressing_style": "path",
                "querystring_auth": True,
                "querystring_expire": AWS_QUERYSTRING_EXPIRE,
            },
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True

EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD")

HUGGINGFACE_API_KEY = os.getenv("HUGGINGFACE_API_KEY")
HF_MODEL = os.getenv("HF_MODEL", "meta-llama/Llama-3.1-8B-Instruct")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022")
AI_INSIGHTS_TIMEOUT_SECONDS = int(os.getenv("AI_INSIGHTS_TIMEOUT_SECONDS", "20"))
AI_INSIGHTS_MAX_TOKENS = int(os.getenv("AI_INSIGHTS_MAX_TOKENS", "1400"))
AI_INSIGHTS_MAX_RESUME_CHARS = int(os.getenv("AI_INSIGHTS_MAX_RESUME_CHARS", "18000"))

cors_raw = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://localhost:80")
CORS_ALLOWED_ORIGINS = [o.strip() for o in cors_raw.split(",") if o.strip()]

csrf_raw = os.getenv("CSRF_TRUSTED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://localhost:80")
CSRF_TRUSTED_ORIGINS = [o.strip() for o in csrf_raw.split(",") if o.strip()]

if not DEBUG and not IS_RUNNING_TESTS:
    if (
        not os.getenv("CORS_ALLOWED_ORIGINS")
        or not CORS_ALLOWED_ORIGINS
        or any(not origin.startswith("https://") for origin in CORS_ALLOWED_ORIGINS)
        or not os.getenv("CSRF_TRUSTED_ORIGINS")
        or not CSRF_TRUSTED_ORIGINS
        or any(not origin.startswith("https://") for origin in CSRF_TRUSTED_ORIGINS)
    ):
        raise ImproperlyConfigured(
            "Production deployment requires explicit HTTPS CORS_ALLOWED_ORIGINS and CSRF_TRUSTED_ORIGINS."
        )

CORS_ALLOW_CREDENTIALS = True
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_COOKIE_SECURE = os.getenv("CSRF_COOKIE_SECURE", "False" if DEBUG else "True").lower() in ("true", "1", "t")
SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "False" if DEBUG else "True").lower() in ("true", "1", "t")

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ),
    'DEFAULT_PERMISSION_CLASSES': (
        'rest_framework.permissions.IsAuthenticated',
    ),
    'DEFAULT_THROTTLE_CLASSES': (
        'rest_framework.throttling.ScopedRateThrottle',
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ),
    'DEFAULT_THROTTLE_RATES': {
        'burst': '60/minute',
        'sustained': '1000/day',
        'anon': '100/day',
        'user': '1000/day',
        'auth_attempt': '5/minute',
        'resume_insights': '3/hour',
    },
}

# Redis & Caching Architecture
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
# Segregated DB indices: DB 0 = Celery Broker, DB 1 = Celery Results, DB 2 = Django Cache, DB 3 = Guardrail Rate Limits
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', f'{REDIS_URL.rstrip("/")}/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', f'{REDIS_URL.rstrip("/")}/1')
CACHE_REDIS_URL = os.getenv('CACHE_REDIS_URL', f'{REDIS_URL.rstrip("/")}/2')
GUARDRAIL_REDIS_URL = os.getenv('GUARDRAIL_REDIS_URL', f'{REDIS_URL.rstrip("/")}/3')

USE_REDIS_CACHE = os.getenv('USE_REDIS_CACHE', 'True').lower() in ('true', '1', 't')

def _is_redis_alive(url: str) -> bool:
    try:
        import redis
        client = redis.Redis.from_url(url, socket_connect_timeout=0.2, socket_timeout=0.2)
        return bool(client.ping())
    except Exception:
        return False

# If Redis is requested but unreachable (e.g. local dev without Docker/Redis), gracefully fall back to LocMemCache
# to prevent DRF throttle / cache timeouts hanging every single HTTP request for 15+ seconds.
if USE_REDIS_CACHE and not IS_RUNNING_TESTS:
    if not _is_redis_alive(REDIS_URL):
        USE_REDIS_CACHE = False

if USE_REDIS_CACHE and not IS_RUNNING_TESTS:
    CACHES = {
        'default': {
            'BACKEND': 'django_redis.cache.RedisCache',
            'LOCATION': CACHE_REDIS_URL,
            'OPTIONS': {
                'CLIENT_CLASS': 'django_redis.client.DefaultClient',
                'IGNORE_EXCEPTIONS': True,  # Graceful fallback: cache miss, not crash
                'SOCKET_CONNECT_TIMEOUT': 1,
                'SOCKET_TIMEOUT': 1,
            },
            'KEY_PREFIX': 'careerconnect',
            'TIMEOUT': 1800,
        }
    }
else:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'careerconnect-locmem',
            'TIMEOUT': 1800,
        }
    }

CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_ALWAYS_EAGER', 'True').lower() in ('true', '1', 't')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_BROKER_TRANSPORT_OPTIONS = {
    'visibility_timeout': 3600,
}

FAISS_INDEX_DIR = Path(os.getenv('FAISS_INDEX_DIR', str(BASE_DIR / 'data' / 'faiss_index')))

SCREENING_AGENT_ENABLED = os.getenv('SCREENING_AGENT_ENABLED', 'True').lower() in ('true', '1', 't')
DIGEST_AGENT_ENABLED = os.getenv('DIGEST_AGENT_ENABLED', 'True').lower() in ('true', '1', 't')
AUTO_APPLY_AGENT_ENABLED = os.getenv('AUTO_APPLY_AGENT_ENABLED', 'True').lower() in ('true', '1', 't')
SCHEDULING_AGENT_ENABLED = os.getenv('SCHEDULING_AGENT_ENABLED', 'True').lower() in ('true', '1', 't')
HARD_WEEKLY_APPLICATION_CEILING = 25

# Security Hardening Settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = os.getenv('SECURE_SSL_REDIRECT', 'False' if DEBUG else 'True').lower() in ('true', '1', 't')
SECURE_HSTS_SECONDS = int(os.getenv('SECURE_HSTS_SECONDS', '0' if DEBUG else '31536000'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = not DEBUG
SECURE_HSTS_PRELOAD = not DEBUG

# Sentry Hook (env-gated)
SENTRY_DSN = os.getenv('SENTRY_DSN')
if SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            integrations=[DjangoIntegration(), CeleryIntegration()],
            traces_sample_rate=float(os.getenv('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
            environment=os.getenv('ENVIRONMENT', 'production' if not DEBUG else 'development'),
            send_default_pii=False,
        )
    except ImportError:
        pass

# Structured JSON Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'json': {
            '()': 'job.logging_formatters.JSONFormatter',
        },
        'standard': {
            'format': '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'json' if not DEBUG else 'standard',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': os.getenv('LOG_LEVEL', 'INFO'),
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'access': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'agents': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'application': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
