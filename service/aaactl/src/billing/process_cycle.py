from __future__ import annotations

from typing import TYPE_CHECKING

import structlog

if TYPE_CHECKING:
    from billing.models import SubscriptionCycle, SubscriptionCycleCharge

log = structlog.get_logger(__name__)


def handle_existing_cycle_charge(
    cycle: SubscriptionCycle,
    existing_cycle_charge: SubscriptionCycleCharge,
) -> SubscriptionCycleCharge | None:
    """Handle a pre-existing SubscriptionCycleCharge.

    Returns a charge ready for processing, or `None` if no further work is
    required (e.g. already paid or zero-amount).
    """

    status = existing_cycle_charge.payment_charge.status

    # Already pending – nothing more to do until processor confirms/denies.
    if status == "pending":
        return existing_cycle_charge

    # Successful charge – honour original behaviour by raising.
    if status == "ok":
        raise OSError("Cycle was already charged successfully")

    # Failed charge – attempt a retry.
    if status == "failed":
        return retry_failed_cycle_charge(cycle, existing_cycle_charge)

    # Any other state leads to no action.
    return None


def retry_failed_cycle_charge(
    cycle: SubscriptionCycle,
    cycle_charge: SubscriptionCycleCharge,
) -> SubscriptionCycleCharge | None:
    """Prepare a new PaymentCharge for a previously-failed attempt."""

    # Delay heavy imports until runtime to avoid circular-import issues.
    from billing.models import PaymentCharge

    cycle_charge.status = "pending"

    # An invoice **must** exist from the first attempt.
    if not cycle.invoice_id:
        raise OSError(
            "Cannot retry failed charge: no invoice is associated with the subscription cycle"
        )

    try:
        invoice_total = cycle.invoice.price
    except Exception:  # Invoice.DoesNotExist also covered
        raise OSError(
            f"Cannot retry failed charge: expected invoice {cycle.invoice_id} not found"
        )

    if invoice_total is not None and float(invoice_total) == 0.0:
        log.info(
            "SubscriptionCycle %s invoice total is 0 - skipping charge retry",
            cycle.id,
        )
        return None

    payment_charge = PaymentCharge.objects.create(
        payment_method=cycle.subscription.payment_method,
        price=invoice_total,
        description=cycle.subscription.charge_description,
    )

    # Ensure invoice points at the new PaymentCharge immediately.
    if cycle.invoice.charge_object_id != payment_charge.id:
        cycle.invoice.charge_object = payment_charge
        cycle.invoice.save(update_fields=["charge_object"])

    cycle_charge.payment_charge = payment_charge
    cycle_charge.save()
    return cycle_charge


def initial_cycle_charge(
    cycle: SubscriptionCycle,
) -> SubscriptionCycleCharge | None:
    """Create Order, Invoice and first PaymentCharge for a cycle."""

    # Delay heavy imports until runtime to avoid circular-import issues.
    from billing.models import Order, PaymentCharge, SubscriptionCycleCharge

    if not cycle.price:
        return None

    # Ensure Order exists.
    if not cycle.order:
        order_number = cycle.create_orders()
        cycle.order = Order.objects.get(order_number=order_number)
        cycle.save(update_fields=["order"])

    # Ensure Invoice exists.
    if not cycle.invoice:
        invoice = cycle.create_invoice(cycle.order.order_number)
        cycle.invoice = invoice
        cycle.save(update_fields=["invoice"])
    else:
        invoice = cycle.invoice

    invoice_total = invoice.price
    if not invoice_total:
        log.info("SubscriptionCycle %s invoice total is 0 - skipping charge", cycle.id)
        return None

    payment_charge = PaymentCharge.objects.create(
        payment_method=cycle.subscription.payment_method,
        price=invoice_total,
        description=cycle.subscription.charge_description,
    )

    # Link invoice → payment immediately.
    invoice.charge_object = payment_charge
    invoice.save(update_fields=["charge_object"])

    cycle_charge = SubscriptionCycleCharge.objects.create(
        subscription_cycle=cycle,
        payment_charge=payment_charge,
        status="pending",
    )
    return cycle_charge


def reconcile_invoice_and_charge(
    cycle: SubscriptionCycle, cycle_charge: SubscriptionCycleCharge
) -> None:
    """Align PaymentCharge amount & linkage with the invoice."""

    invoice = cycle.invoice  # Must exist

    # Keep amounts in sync.
    if invoice.price != cycle_charge.payment_charge.price:
        cycle_charge.payment_charge.price = invoice.price
        cycle_charge.payment_charge.save(update_fields=["price"])

    # Ensure linkage.
    if invoice.charge_object != cycle_charge.payment_charge:
        invoice.charge_object = cycle_charge.payment_charge
        invoice.save(update_fields=["charge_object"])

    log.debug(
        f"{cycle_charge.payment_charge.id}",
        details=cycle_charge.payment_charge.details,
        price=cycle_charge.payment_charge.price,
    )
