from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Count
from application.models import Application


class Command(BaseCommand):
    help = (
        "Restores soft-archived applicant/application records by resetting archived_at=None and archive_batch=''. "
        "Can restore a specific batch with --batch <id> or all archived records with --all."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch",
            type=str,
            default=None,
            help="Specific archive batch ID to restore.",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            default=False,
            help="Restore all soft-archived application records regardless of batch ID.",
        )

    def handle(self, *args, **options):
        batch_id = options["batch"]
        restore_all = options["all"]

        if not batch_id and not restore_all:
            raise CommandError("Please specify either --batch <batch_id> or --all to restore archived applicants.")

        qs = Application.objects.filter(archived_at__isnull=False)
        if batch_id:
            qs = qs.filter(archive_batch=batch_id)

        target_count = qs.count()

        self.stdout.write(self.style.MIGRATE_HEADING("=== Restore Archived Applicants ==="))

        if target_count == 0:
            msg = f"No archived applications found for batch '{batch_id}'." if batch_id else "No archived applications found in database."
            self.stdout.write(self.style.WARNING(msg))
            return

        self.stdout.write(f"Applications to restore: {target_count}")
        for jc in qs.values("job_id", "job__title").annotate(c=Count("id")).order_by("-c"):
            self.stdout.write(f"  - Job #{jc['job_id']} '{jc['job__title']}': {jc['c']}")

        with transaction.atomic():
            restored_count = qs.update(
                archived_at=None,
                archive_batch="",
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n[SUCCESS] Successfully restored {restored_count} applications.\n"
                f"All restored records are now active and will appear on the recruiter dashboard again."
            )
        )
