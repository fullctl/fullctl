# Generated by Django 2.2.20 on 2021-06-03 08:38

import django_inet.models
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("django_fullctl", "0006_auto_20210603_0542"),
    ]

    operations = [
        migrations.AddField(
            model_name="auditlog",
            name="ip_address",
            field=django_inet.models.IPAddressField(
                blank=True, max_length=39, null=True
            ),
        ),
    ]