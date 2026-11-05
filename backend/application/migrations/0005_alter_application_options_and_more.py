from django.conf import settings
from django.db import migrations, models

try:
    from django.contrib.postgres.operations import AddIndexConcurrently as _PgAddIndexConcurrently
except ImportError:
    _PgAddIndexConcurrently = migrations.AddIndex

class AddIndexConcurrently(_PgAddIndexConcurrently):
    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor != 'postgresql':
            model = to_state.apps.get_model(app_label, self.model_name)
            schema_editor.add_index(model, self.index)
        else:
            super().database_forwards(app_label, schema_editor, from_state, to_state)

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        if schema_editor.connection.vendor != 'postgresql':
            model = from_state.apps.get_model(app_label, self.model_name)
            schema_editor.remove_index(model, self.index)
        else:
            super().database_backwards(app_label, schema_editor, from_state, to_state)


class Migration(migrations.Migration):
    atomic = False

    dependencies = [
        ('application', '0004_alter_application_unique_together_and_more'),
        ('jobs', '0002_alter_job_options_job_job_active_expires_idx_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='application',
            options={'ordering': ['-applied_at']},
        ),
        AddIndexConcurrently(
            model_name='application',
            index=models.Index(fields=['job', 'status'], name='app_job_status_idx'),
        ),
        AddIndexConcurrently(
            model_name='application',
            index=models.Index(fields=['candidate', 'status'], name='app_cand_status_idx'),
        ),
        AddIndexConcurrently(
            model_name='application',
            index=models.Index(fields=['status', '-applied_at'], name='app_status_applied_idx'),
        ),
        AddIndexConcurrently(
            model_name='application',
            index=models.Index(fields=['candidate', 'job'], name='app_cand_job_idx'),
        ),
        AddIndexConcurrently(
            model_name='application',
            index=models.Index(fields=['job', 'archived_at'], name='app_job_archived_idx'),
        ),
        AddIndexConcurrently(
            model_name='application',
            index=models.Index(fields=['candidate', 'archived_at'], name='app_cand_archived_idx'),
        ),
        AddIndexConcurrently(
            model_name='applicationstatuslog',
            index=models.Index(fields=['application', '-changed_at'], name='app_status_log_idx'),
        ),
        AddIndexConcurrently(
            model_name='applicationstatuslog',
            index=models.Index(fields=['new_status', '-changed_at'], name='app_log_status_idx'),
        ),
    ]
