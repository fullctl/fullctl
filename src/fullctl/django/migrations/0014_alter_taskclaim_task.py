# Generated by Django 3.2.4 on 2021-08-05 12:01

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_fullctl", "0013_auto_20210805_1200"),
    ]

    operations = [
        migrations.AlterField(
            model_name="taskclaim",
            name="task",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE, to="django_fullctl.task"
            ),
        ),
    ]
