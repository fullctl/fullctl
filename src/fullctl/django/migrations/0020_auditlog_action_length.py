# Generated by Django 3.2.14 on 2022-08-11 11:54

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_fullctl", "0019_default_org"),
    ]

    operations = [
        migrations.AlterField(
            model_name="auditlog",
            name="action",
            field=models.CharField(max_length=128),
        ),
    ]
