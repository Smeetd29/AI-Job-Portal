from datetime import datetime
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Count
from django.utils import timezone
from application.models import Application


class Command(BaseCommand):
    help = (
        "Soft-archives applicant/application records so testing starts from a clean slate. "
        "NO records are deleted; all records remain in the database with an archived_at timestamp."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Simulate the archiving operation without making any database changes (default).",
        )
        parser.add_argument(
            "--confirm",
            action="store_true",
            default=False,
            help="Perform the actual soft-archive update in the database.",
        )
        parser.add_argument(
            "--job",
            type=int,
            default=None,
            help="Optional job ID to limit the archiving to applications for that job.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        confirm = options["confirm"]
        job_id = options["job"]

        # Default is dry-run unless --confirm is explicitly passed
        is_dry_run = not confirm or dry_run

        qs = Application.objects.filter(archived_at__isnull=True)
        if job_id is not None:
            qs = qs.filter(job_id=job_id)

        target_count = qs.count()

        self.stdout.write(self.style.MIGRATE_HEADING("=== Reset Test Applicants (Soft-Archive) ==="))

        if target_count == 0:
            self.stdout.write(self.style.WARNING("No active (unarchived) applications found to archive."))
            return

        # Print breakdown of records to be archived
        self.stdout.write(f"Target applications to archive: {target_count}")
        self.stdout.write("\nBreakdown by Status:")
        for sc in qs.values("status").annotate(c=Count("id")).order_by("-c"):
            self.stdout.write(f"  - {sc['status']}: {sc['c']}")

        self.stdout.write("\nBreakdown by Job:")
        for jc in qs.values("job_id", "job__title").annotate(c=Count("id")).order_by("-c"):
            self.stdout.write(f"  - Job #{jc['job_id']} '{jc['job__title']}': {jc['c']}")

        if is_dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "\n[DRY RUN MODE] No changes were made to the database. "
                    "Run with --confirm to perform the actual soft-archive."
                )
            )
            return

        # Actually archive inside atomic transaction
        now = timezone.now()
        batch_id = f"batch_{now.strftime('%Y%m%d_%H%M%S')}"

        with transaction.atomic():
            updated_count = qs.update(
                archived_at=now,
                archive_batch=batch_id,
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n[SUCCESS] Soft-archived {updated_count} applications.\n"
                f"Archive Batch ID: {batch_id}\n"
                f"Timestamp: {now.isoformat()}\n"
                f"Recruiter dashboard will now show 0 applicants for these jobs.\n"
                f"To restore these records, run:\n"
                f"  python manage.py restore_archived_applicants --batch {batch_id}"
            )
        )
