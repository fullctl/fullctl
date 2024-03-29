# Generated by Django 3.2.16 on 2023-01-31 14:05

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_fullctl", "0025_auto_20221025_1215"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(
                fields=["org_id", "action"], name="django_full_org_id_29fa6f_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(fields=["user"], name="django_full_user_id_36d22e_idx"),
        ),
        migrations.AddIndex(
            model_name="auditlog",
            index=models.Index(
                fields=["object_type", "object_id"],
                name="django_full_object__5cc546_idx",
            ),
        ),
    ]
