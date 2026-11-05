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
        ('agents', '0001_initial'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('jobs', '0002_alter_job_options_job_job_active_expires_idx_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameIndex(
            model_name='agentaction',
            new_name='act_user_status_idx',
            old_name='agents_agen_user_id_e73b80_idx',
        ),
        migrations.RenameIndex(
            model_name='agentaction',
            new_name='act_type_status_idx',
            old_name='agents_agen_agent_t_88b126_idx',
        ),
        migrations.RenameIndex(
            model_name='agentaction',
            new_name='act_job_user_idx',
            old_name='agents_agen_job_id_97da92_idx',
        ),
        AddIndexConcurrently(
            model_name='agentaction',
            index=models.Index(fields=['status', '-created_at'], name='act_status_created_idx'),
        ),
        AddIndexConcurrently(
            model_name='agentrun',
            index=models.Index(fields=['status', '-started_at'], name='agent_run_status_idx'),
        ),
        AddIndexConcurrently(
            model_name='agentrun',
            index=models.Index(fields=['agent_type', 'status'], name='agent_run_type_status_idx'),
        ),
        AddIndexConcurrently(
            model_name='agentrun',
            index=models.Index(fields=['user', '-started_at'], name='agent_run_user_idx'),
        ),
    ]
