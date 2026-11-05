from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from copilot.models import QueueItem


class Command(BaseCommand):
    help = "Soft-archives QueueItem applications in career_copilot without deleting records."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", default=False)
        parser.add_argument("--confirm", action="store_true", default=False)
        parser.add_argument("--job", type=str, default=None)

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        confirm = options["confirm"]
        job_id = options["job"]

        is_dry_run = not confirm or dry_run
        qs = QueueItem.objects.filter(archived_at__isnull=True)
        if job_id:
            qs = qs.filter(job_id=job_id)

        target_count = qs.count()
        self.stdout.write(self.style.MIGRATE_HEADING("=== Reset Test Queue Items (Career Co-Pilot) ==="))

        if target_count == 0:
            self.stdout.write(self.style.WARNING("No active QueueItem records found."))
            return

        self.stdout.write(f"Target queue items to archive: {target_count}")
        for sc in qs.values("status").annotate(c=Count("id")).order_by("-c"):
            self.stdout.write(f"  - {sc['status']}: {sc['c']}")

        if is_dry_run:
            self.stdout.write(self.style.WARNING("[DRY RUN MODE] No changes made. Pass --confirm to archive."))
            return

        now = timezone.now()
        batch_id = f"batch_{now.strftime('%Y%m%d_%H%M%S')}"

        with transaction.atomic():
            updated = qs.update(archived_at=now, archive_batch=batch_id)

        self.stdout.write(self.style.SUCCESS(f"[SUCCESS] Soft-archived {updated} QueueItems under batch {batch_id}"))
