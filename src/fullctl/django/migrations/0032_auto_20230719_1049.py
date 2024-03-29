# Generated by Django 3.2.20 on 2023-07-19 10:49

import django.db.models.deletion
import django.db.models.manager
import django_handleref.models
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_fullctl", "0031_auto_20230310_2152"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrganizationFile",
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
                ("name", models.CharField(max_length=255)),
                ("content", models.BinaryField()),
                ("content_type", models.CharField(max_length=255)),
                ("public", models.BooleanField(default=False)),
                (
                    "org",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="django_fullctl.organization",
                    ),
                ),
            ],
            options={
                "verbose_name": "Organization File",
                "verbose_name_plural": "Organization Files",
                "db_table": "fullctl_organization_file",
            },
            managers=[
                ("handleref", django.db.models.manager.Manager()),
            ],
        ),
    ]
