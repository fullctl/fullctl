# Generated by Django 3.2.17 on 2023-03-10 12:40

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("django_fullctl", "0027_request_response"),
    ]

    operations = [
        migrations.AddField(
            model_name="request",
            name="identifier",
            field=models.CharField(db_index=True, default=1, max_length=255),
            preserve_default=False,
        ),
    ]
