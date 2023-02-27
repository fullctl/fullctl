# Generated by Django 3.2.4 on 2021-07-08 07:52

import django.db.models.deletion
import django.db.models.manager
import django_handleref.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("django_fullctl", "0008_managementtask"),
    ]

    operations = [
        migrations.CreateModel(
            name="TaskClaim",
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
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("ok", "Ok"),
                            ("pending", "Pending"),
                            ("deactivated", "Deactivated"),
                            ("failed", "Failed"),
                            ("expired", "Expired"),
                        ],
                        default="ok",
                        max_length=12,
                    ),
                ),
                ("task_id", models.PositiveIntegerField()),
                ("worker_id", models.CharField(max_length=255)),
                (
                    "task_type",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.contenttype",
                    ),
                ),
            ],
            options={
                "verbose_name": "Claimed Task",
                "verbose_name_plural": "Claimed Tasks",
                "db_table": "fullctl_task_claim",
                "unique_together": {("task_type", "task_id")},
            },
            managers=[
                ("handleref", django.db.models.manager.Manager()),
            ],
        ),
    ]
