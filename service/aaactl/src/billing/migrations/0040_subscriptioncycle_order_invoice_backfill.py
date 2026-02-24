from django.db import migrations


def _backfill_cycle_invoice_order(apps, schema_editor):
    SubscriptionCycle = apps.get_model("billing", "SubscriptionCycle")
    InvoiceLine = apps.get_model("billing", "InvoiceLine")

    qs = SubscriptionCycle.handleref.filter(invoice__isnull=True)

    for cycle in qs.iterator():
        invoice_line = (
            InvoiceLine.handleref.filter(
                subscription_cycle_product__subscription_cycle_id=cycle.id
            )
            .select_related("invoice__order")
            .first()
        )

        if not invoice_line:
            # No invoice found – nothing we can link automatically.
            continue

        invoice = invoice_line.invoice
        order = invoice.order

        # Direct DB update to avoid project-level side-effects
        SubscriptionCycle.handleref.filter(id=cycle.id).update(
            invoice_id=invoice.id,
            order_id=order.id,
        )


class Migration(migrations.Migration):

    dependencies = [
        ("billing", "0039_subscriptioncycle_order_invoice"),
    ]

    operations = [
        migrations.RunPython(
            code=_backfill_cycle_invoice_order,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
