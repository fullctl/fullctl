# Generated by Django 3.2.4 on 2021-10-06 13:11

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("django_fullctl", "0016_task_limit_id"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="organizationuser",
            options={
                "verbose_name": "Organization User",
                "verbose_name_plural": "Organization Users",
            },
        ),
    ]