import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("django_auditctl", "0011_event_auditctl_en_object__565726_idx"),
    ]

    operations = [
        migrations.AddField(
            model_name="organizationemailalert",
            name="threshold",
            field=models.PositiveIntegerField(
                default=1,
                help_text="Number of consecutive error events required before sending an alert. Set to 1 for immediate alerting (default behavior).",
                validators=[django.core.validators.MinValueValidator(1)],
            ),
        ),
        migrations.AddField(
            model_name="organizationemailalert",
            name="last_notified_at",
            field=models.DateTimeField(
                blank=True,
                help_text="Timestamp of the last alert notification sent for this email.",
                null=True,
            ),
        ),
    ]
