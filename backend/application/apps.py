import os
import sys
import threading
from django.apps import AppConfig

class ApplicationConfig(AppConfig):
    name = 'application'

    def ready(self):
        try:
            import application.signals  # noqa: F401
        except Exception:
            pass

        skip_commands = {'migrate', 'makemigrations', 'test', 'check', 'collectstatic', 'createsuperuser'}
        if any(cmd in sys.argv for cmd in skip_commands):
            return

        if os.environ.get('RUN_MAIN') == 'true' or not os.environ.get('DJANGO_SETTINGS_MODULE'):
            def _warmup():
                try:
                    from application.ai.pipeline import MatchingPipeline
                    MatchingPipeline.get_default()
                except Exception:
                    pass

            thread = threading.Thread(target=_warmup, daemon=True, name="ai_pipeline_warmup")
            thread.start()
