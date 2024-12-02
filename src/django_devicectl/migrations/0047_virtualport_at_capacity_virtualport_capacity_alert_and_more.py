from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("django_devicectl", "0046_macaddress"),
    ]

    operations = [
        migrations.AddField(
            model_name="virtualport",
            name="at_capacity",
            field=models.DateTimeField(
                default=None,
                help_text="The last time the device was at capacity above the threshold.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="virtualport",
            name="capacity_alert",
            field=models.PositiveIntegerField(
                default=0,
                help_text="The amount of times the device has been at capacity.",
            ),
        ),
        migrations.AddField(
            model_name="virtualport",
            name="capacity_notified_ix",
            field=models.DateTimeField(
                default=None,
                help_text="The last time a notification was sent for the IX operator.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="virtualport",
            name="capacity_notified_net",
            field=models.DateTimeField(
                default=None,
                help_text="The last time a notification was sent for the IX member.",
                null=True,
            ),
        ),
    ]
