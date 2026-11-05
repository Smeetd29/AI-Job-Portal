from __future__ import annotations

import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'job.settings')

app = Celery('careerconnect')

app.config_from_object('django.conf:settings', namespace='CELERY')

app.autodiscover_tasks()

app.conf.beat_schedule = {
    'digest-periodic-dispatch': {
        'task': 'agents.tasks.run_digest_dispatch',
        'schedule': crontab(hour=8, minute=0, day_of_week=1),
    },
    'auto-apply-daily-scan': {
        'task': 'agents.tasks.run_auto_apply_scan',
        'schedule': crontab(hour=9, minute=0),
    },
    'sweep-expired-proposals-hourly': {
        'task': 'agents.tasks.sweep_expired_proposals',
        'schedule': crontab(minute='*/30'),
    },
    'rebuild-faiss-index-daily': {
        'task': 'application.ai.tasks.rebuild_faiss_index_task',
        'schedule': crontab(hour=2, minute=0),
    },
}
