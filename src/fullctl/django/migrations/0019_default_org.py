# Generated by Django 3.2.8 on 2022-03-03 13:15

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("django_fullctl", "0018_task_schedule"),
    ]

    operations = [
        migrations.AddField(
            model_name="organizationuser",
            name="is_default",
            field=models.BooleanField(default=False),
        ),
    ]
