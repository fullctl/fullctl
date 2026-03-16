from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("django_ixctl", "0043_networkmeta_web_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="routeserver",
            name="liveness",
            field=models.DateTimeField(
                blank=True,
                help_text="Last config liveness timestamp",
                null=True,
            ),
        ),
    ]
