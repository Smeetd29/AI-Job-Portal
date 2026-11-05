from django.core.management.base import BaseCommand
from users.models import User, RecruiterProfile
from jobs.models import Job

class Command(BaseCommand):
    help = "Seed recommendation jobs"

    def handle(self, *args, **options):
        recruiter, _ = User.objects.get_or_create(
            username="Jeet",
            defaults={"email": "jeet@novatech.io", "is_recruiter": True, "is_candidate": False}
        )
        recruiter.set_password("12345678")
        recruiter.save()
        RecruiterProfile.objects.get_or_create(user=recruiter, defaults={"company_name": "NovaTech AI Labs"})

        jobs = [
            ("Python Backend Engineer", "Engineering", "Full Time", "Remote", 100000, "Python Django REST"),
            ("Frontend React Developer", "Engineering", "Full Time", "Remote", 90000, "React Tailwind JavaScript"),
        ]
        for title, cat, jt, lt, pay, desc in jobs:
            Job.objects.update_or_create(
                recruiter=recruiter, title=title,
                defaults={"category": cat, "job_type": jt, "location_type": lt, "pay_amount": pay, "description": desc, "is_active": True}
            )
        self.stdout.write(self.style.SUCCESS("[OK] Seeded jobs"))
