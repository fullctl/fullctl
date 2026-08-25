from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("fullctl_testapp", "0001_initial"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="request",
            constraint=models.UniqueConstraint(
                fields=("source", "url"),
                name="fullctl_testapp_request_unique_cache_key",
            ),
        ),
    ]
