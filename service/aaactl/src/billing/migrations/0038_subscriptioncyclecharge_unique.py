from django.db import migrations, models
from django.db.models import Count


def deduplicate_cycle_charges(apps, schema_editor):
    SubscriptionCycleCharge = apps.get_model("billing", "SubscriptionCycleCharge")
    db_alias = schema_editor.connection.alias

    duplicates = (
        SubscriptionCycleCharge.handleref.using(db_alias)
        .values("subscription_cycle")
        .annotate(cnt=Count("id"))
        .filter(cnt__gt=1)
    )

    for dup in duplicates:
        cycle_id = dup["subscription_cycle"]
        charges = (
            SubscriptionCycleCharge.handleref.using(db_alias)
            .filter(subscription_cycle_id=cycle_id)
            .order_by("-id")
        )
        keep = charges.first()
        # Delete older duplicate records, keeping the most recent
        charges.exclude(id=keep.id).delete()


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0037_subscription_billing_paused"),
    ]

    operations = [
        migrations.RunPython(deduplicate_cycle_charges, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="subscriptioncyclecharge",
            constraint=models.UniqueConstraint(
                fields=("subscription_cycle",), name="uniq_cycle_charge"
            ),
        ),
    ] 