# Generated by Django 3.2.4 on 2021-07-07 13:36

from django.db import migrations, models
import django.db.models.deletion
import django.db.models.manager
import django_handleref.models
import fullctl.django.tasks.util


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("django_fullctl", "0007_auditlog_ip_address"),
    ]

    operations = [
        migrations.CreateModel(
            name="ManagementTask",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "created",
                    django_handleref.models.CreatedDateTimeField(
                        auto_now_add=True, verbose_name="Created"
                    ),
                ),
                (
                    "updated",
                    django_handleref.models.UpdatedDateTimeField(
                        auto_now=True, verbose_name="Updated"
                    ),
                ),
                ("version", models.IntegerField(default=0)),
                ("op", models.CharField(max_length=255)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("completed", "Completed"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=255,
                    ),
                ),
                (
                    "param_json",
                    models.TextField(
                        blank=True,
                        help_text="json containing args and kwargs",
                        null=True,
                    ),
                ),
                (
                    "error",
                    models.TextField(
                        blank=True,
                        help_text="if the task failed will contain traceback or error info",
                        null=True,
                    ),
                ),
                (
                    "output",
                    models.TextField(
                        blank=True,
                        help_text="task output - can also be used to store results",
                        null=True,
                    ),
                ),
                (
                    "timeout",
                    models.IntegerField(
                        blank=True,
                        default=None,
                        help_text="task timeout in seconds",
                        null=True,
                    ),
                ),
                (
                    "time",
                    models.FloatField(default=0.0, help_text="time sepnt in seconds"),
                ),
                (
                    "source",
                    models.CharField(
                        blank=True,
                        default=fullctl.django.tasks.util.worker_id,
                        help_text="host id where task was triggered",
                        max_length=255,
                        null=True,
                    ),
                ),
                (
                    "queue_id",
                    models.CharField(
                        blank=True,
                        help_text="task queue id (celery task id or orm worker id)",
                        max_length=255,
                        null=True,
                        unique=True,
                    ),
                ),
                ("parent_id", models.PositiveIntegerField(blank=True, null=True)),
                (
                    "parent_type",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.contenttype",
                    ),
                ),
            ],
            options={
                "verbose_name": "Django Management Task",
                "verbose_name_plural": "Django Management Tasks",
                "db_table": "fullctl_task_command",
            },
            managers=[
                ("handleref", django.db.models.manager.Manager()),
            ],
        ),
    ]
