from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0038_subscriptioncyclecharge_unique"),
    ]

    operations = [
        migrations.AddField(
            model_name="subscriptioncycle",
            name="order",
            field=models.OneToOneField(
                null=True,
                blank=True,
                on_delete=models.SET_NULL,
                related_name="subscription_cycle",
                to="billing.order",
            ),
        ),
        migrations.AddField(
            model_name="subscriptioncycle",
            name="invoice",
            field=models.OneToOneField(
                null=True,
                blank=True,
                on_delete=models.SET_NULL,
                related_name="subscription_cycle",
                to="billing.invoice",
            ),
        ),
    ]
