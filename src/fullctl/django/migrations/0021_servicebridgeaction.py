# Generated by Django 3.2.15 on 2022-09-06 14:37

import django.db.models.manager
import django_handleref.models
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("django_fullctl", "0020_auditlog_action_length"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceBridgeAction",
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
                ("name", models.CharField(max_length=255, unique=True)),
                (
                    "reference",
                    models.CharField(
                        help_text="should be {module_path}.{class_name} of the service bridge class",
                        max_length=255,
                    ),
                ),
                (
                    "target",
                    models.CharField(
                        help_text="should be {app_label}.{mode_name} of the target model",
                        max_length=255,
                    ),
                ),
                (
                    "description",
                    models.CharField(blank=True, max_length=255, null=True),
                ),
                (
                    "action",
                    models.CharField(
                        choices=[("pull", "Pull"), ("push", "Push")],
                        default="pull",
                        max_length=8,
                    ),
                ),
                (
                    "data_map",
                    models.JSONField(
                        blank=True,
                        default={},
                        help_text="map reference fields to target fields - only fields specified here will be affected by this action. Leave empty to use the default definitions for the model, if they exist.",
                        null=True,
                    ),
                ),
            ],
            options={
                "verbose_name": "Service Bridge Action",
                "verbose_name_plural": "Service Bridge Actions",
                "db_table": "fullctl_service_bridge_action",
            },
            managers=[
                ("handleref", django.db.models.manager.Manager()),
            ],
        ),
    ]