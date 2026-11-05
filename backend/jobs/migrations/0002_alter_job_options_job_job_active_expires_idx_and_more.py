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
        ('jobs', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='job',
            options={'ordering': ['-created_at']},
        ),
        AddIndexConcurrently(
            model_name='job',
            index=models.Index(fields=['is_active', 'expires_at'], name='job_active_expires_idx'),
        ),
        AddIndexConcurrently(
            model_name='job',
            index=models.Index(fields=['is_active', '-created_at'], name='job_active_created_idx'),
        ),
        AddIndexConcurrently(
            model_name='job',
            index=models.Index(fields=['category', 'is_active'], name='job_category_active_idx'),
        ),
        AddIndexConcurrently(
            model_name='job',
            index=models.Index(fields=['recruiter', '-created_at'], name='job_recruiter_created_idx'),
        ),
        AddIndexConcurrently(
            model_name='job',
            index=models.Index(fields=['location_type', 'is_active'], name='job_location_active_idx'),
        ),
        AddIndexConcurrently(
            model_name='job',
            index=models.Index(fields=['job_type', 'is_active'], name='job_type_active_idx'),
        ),
    ]
