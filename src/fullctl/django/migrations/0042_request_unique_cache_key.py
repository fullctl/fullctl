from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("django_fullctl", "0041_merge_20260514_1956"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="request",
            constraint=models.UniqueConstraint(
                fields=("source", "url"),
                name="django_fullctl_request_unique_cache_key",
            ),
        ),
    ]
