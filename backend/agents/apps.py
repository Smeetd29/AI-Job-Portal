from django.apps import AppConfig
from django.db.models.signals import post_save

def on_application_saved(sender, instance, created, **kwargs):
    from agents.guardrails import is_agent_enabled
    from agents.tasks import run_screening_agent, run_scheduling_agent
    if created and instance.status == "PENDING":
        if is_agent_enabled("screening"):
            try: run_screening_agent.delay(instance.id)
            except Exception: run_screening_agent(instance.id)
    elif not created and instance.status == "SHORTLISTED":
        if is_agent_enabled("scheduling"):
            if not instance.slot_proposals.filter(status__in=["pending", "confirmed"]).exists():
                try: run_scheduling_agent.delay(instance.id)
                except Exception: run_scheduling_agent(instance.id)

class AgentsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'agents'

    def ready(self):
        from application.models import Application
        post_save.connect(on_application_saved, sender=Application)
