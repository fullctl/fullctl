# Generated by Django 4.2.10 on 2024-04-22 20:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("django_fullctl", "0033_task_fullctl_tas_status_d88ee1_idx_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="requeued",
            field=models.BooleanField(default=False, help_text="task was requeued"),
        ),
    ]
