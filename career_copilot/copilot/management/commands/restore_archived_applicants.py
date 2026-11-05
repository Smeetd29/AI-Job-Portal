from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from copilot.models import QueueItem


class Command(BaseCommand):
    help = "Restores soft-archived QueueItem records in career_copilot."

    def add_arguments(self, parser):
        parser.add_argument("--batch", type=str, default=None)
        parser.add_argument("--all", action="store_true", default=False)

    def handle(self, *args, **options):
        batch_id = options["batch"]
        restore_all = options["all"]

        if not batch_id and not restore_all:
            raise CommandError("Please specify --batch <batch_id> or --all to restore.")

        qs = QueueItem.objects.filter(archived_at__isnull=False)
        if batch_id:
            qs = qs.filter(archive_batch=batch_id)

        target_count = qs.count()
        if target_count == 0:
            self.stdout.write(self.style.WARNING("No archived QueueItem records found."))
            return

        with transaction.atomic():
            restored = qs.update(archived_at=None, archive_batch="")

        self.stdout.write(self.style.SUCCESS(f"[SUCCESS] Restored {restored} QueueItems."))
