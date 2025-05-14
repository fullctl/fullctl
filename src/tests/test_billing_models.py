import uuid
from datetime import datetime, timedelta, timezone

import pytest
from django.contrib.contenttypes.models import ContentType
from django.db.models import ProtectedError

from billing.models import (
    InvoiceLine,
    Ledger,
    OrderHistory,
    OrderLine,
    Payment,
    SubscriptionCycle,
    SubscriptionCycleProduct,
    SubscriptionProduct,
    Withdrawal,
)


def test_product_group(db, billing_objects):
    assert str(billing_objects.product.group) == "Test Group"
    assert str(billing_objects.product_subscription_fixed.group) == "Test Group"
    assert str(billing_objects.product_subscription_metered.group) == "Test Group"


def test_recurring_products(db, billing_objects):
    assert billing_objects.product.is_recurring_product is False
    assert billing_objects.product_subscription_fixed.is_recurring_product is True
    assert billing_objects.product_subscription_metered.is_recurring_product is True


def test_recurring_product_type(db, billing_objects):
    assert (
        billing_objects.product_subscription_fixed.recurring_product.type_description
        == "Fixed Price"
    )
    assert (
        billing_objects.product_subscription_metered.recurring_product.type_description
        == "Metered Usage"
    )

    # test_product_modifier():
    """
    Test how product modifiers affects price.
    """


def test_subscription_products(db, billing_objects):
    """
    Test adding a product to subscription.
    """
    subscription = billing_objects.monthly_subscription
    product_subscription_fixed = billing_objects.product_subscription_fixed
    subscription.add_product(product_subscription_fixed)
    assert SubscriptionProduct.objects.filter(subscription=subscription).count() == 2


def test_subscription_cycle_start(db, billing_objects):
    """
    Test how subscription_cycle is calculated in terms of time.
    """
    subscription = billing_objects.monthly_subscription

    # Test subscription_cycle start
    assert subscription.subscription_cycle_start is None
    subscription.start_subscription_cycle()
    assert subscription.subscription_cycle_start == datetime.now(timezone.utc).date()

    # Cannot re-start with active
    with pytest.raises(OSError):
        subscription.start_subscription_cycle()


def test_subscription_cycle(db, billing_objects):
    """
    Test how subscription_cycle is calculated in terms of time and frequency.
    """
    m_subscription = billing_objects.monthly_subscription

    # Start a subscription_cycle two months ago
    two_months_ago = (datetime.now(timezone.utc) - timedelta(days=60)).date()
    m_subscription.start_subscription_cycle(two_months_ago)
    assert m_subscription.subscription_cycle is None

    # Need to address January rollover
    expected_end = SubscriptionCycle.objects.first().start.month + 1
    if expected_end > 12:
        expected_end -= 12

    assert expected_end == SubscriptionCycle.objects.first().end.month

    # now start a subscription_cycle two weeks ago
    two_weeks_ago = (datetime.now(timezone.utc) - timedelta(days=14)).date()
    m_subscription.start_subscription_cycle(two_weeks_ago)
    assert m_subscription.subscription_cycle
    assert SubscriptionCycle.objects.count() == 2


def test_end_subscription_cycle(db, billing_objects, mocker):
    # Overrides creating the charge on Stripe's end.
    mocker.patch(
        "billing.payment_processors.stripe.stripe.PaymentIntent.create",
        return_value={"id": 1234, "receipt_url": "https://example.com"},
    )

    subscription = billing_objects.monthly_subscription
    two_weeks_ago = (datetime.now(timezone.utc) - timedelta(days=14)).date()
    subscription.start_subscription_cycle(two_weeks_ago)

    subscription.payment_method = billing_objects.payment_method
    subscription.save()

    # FIXME - This doesn't seem to be the test we want
    # but currently there is no way to force end a subscription_cycle (?)
    with pytest.raises(OSError):
        subscription.end_subscription_cycle()


def test_subscription_cycle_charge(db, billing_objects, mocker):
    # Overrides creating the charge on Stripe's end.
    mocker.patch(
        "billing.payment_processors.stripe.stripe.PaymentIntent.create",
        return_value={"id": 1234, "receipt_url": "https://example.com"},
    )
    subscription = billing_objects.monthly_subscription
    subscription.payment_method = billing_objects.payment_method
    two_weeks_ago = (datetime.now(timezone.utc) - timedelta(days=14)).date()
    subscription.start_subscription_cycle(two_weeks_ago)
    subscription_cycle = subscription.subscription_cycle_set.first()

    subscription_cycle.update_usage(subscription.subscription_product_set.first(), 1)

    assert subscription_cycle.price > 0

    subscription_cycle.charge()
    subscription_cycle_charge = subscription_cycle.subscription_cycle_charge_set.first()
    payment_charge = subscription_cycle_charge.payment_charge

    assert subscription_cycle_charge.subscription_cycle == subscription_cycle
    assert payment_charge.price == subscription_cycle.price
    assert payment_charge.description == subscription.charge_description


def test_subscription_cycle_charge_exists(db, billing_objects, mocker):
    # Overrides creating the charge on Stripe's end.
    mocker.patch(
        "billing.payment_processors.stripe.stripe.PaymentIntent.create",
        return_value={"id": 1234, "receipt_url": "https://example.com"},
    )
    subscription = billing_objects.monthly_subscription
    subscription.payment_method = billing_objects.payment_method
    two_weeks_ago = (datetime.now(timezone.utc) - timedelta(days=14)).date()
    subscription.start_subscription_cycle(two_weeks_ago)
    subscription_cycle = subscription.subscription_cycle_set.first()

    subscription_cycle.update_usage(subscription.subscription_product_set.first(), 1)

    assert subscription_cycle.price > 0

    subscription_cycle.charge()

    subscription_cycle_charge = subscription_cycle.subscription_cycle_charge_set.first()

    # Returns charge if charge is still "pending"
    assert subscription_cycle.charge() == subscription_cycle_charge

    # Now we set status of payment charge from ok to pending
    subscription_cycle_charge = subscription_cycle.subscription_cycle_charge_set.first()
    payment_charge = subscription_cycle_charge.payment_charge
    
    # Verify initial status
    assert subscription_cycle_charge.status == "pending"
    
    payment_charge.status = "ok"
    payment_charge.save()
    
    subscription_cycle.refresh_from_db()

    # Raises error if we retry an "ok" charge
    with pytest.raises(OSError, match="Cycle was already charged successfully"):
        subscription_cycle.charge()


def test_calc_subscription_charge(db, billing_objects):
    """
    Test how subscription charges are calculated.
    """

    # Create subscription_cycle
    subscription = billing_objects.monthly_subscription
    two_months_ago = (datetime.now(timezone.utc) - timedelta(days=60)).date()
    subscription_cycle = subscription.start_subscription_cycle(two_months_ago)

    # Create product subscriptions

    product_fixed = billing_objects.product_subscription_fixed
    subscription.add_product(product_fixed)
    fixed_subscription_product = product_fixed.subscription_set.first()

    product_metered = billing_objects.product_subscription_metered
    subscription.add_product(product_metered)
    metered_subscription_product = product_metered.subscription_set.first()

    # Create Subscription Cycle Products
    fixed_subscription_cycle_product = SubscriptionCycleProduct.objects.create(
        subscription_cycle=subscription_cycle,
        subscription_product=fixed_subscription_product,
        usage=1,
    )

    assert fixed_subscription_cycle_product.price == 125.99

    metered_subscription_cycle_product = SubscriptionCycleProduct.objects.create(
        subscription_cycle=subscription_cycle,
        subscription_product=metered_subscription_product,
        usage=0,
    )

    # Adjust usage
    assert metered_subscription_cycle_product.price == 0
    metered_subscription_cycle_product.usage = 50
    metered_subscription_cycle_product.save()

    assert metered_subscription_cycle_product.price == 25

    # Get price for whole subscription_cycle
    assert subscription_cycle.price == 150.99

    # test_subscription_modifier():
    """
    # Test subscription modifiers.
    """


def test_order_history(db, billing_objects, mocker):
    mocker.patch(
        "billing.payment_processors.stripe.stripe.PaymentIntent.create",
        return_value={"id": 1234, "receipt_url": "https://example.com"},
    )
    subscription = billing_objects.monthly_subscription
    subscription.payment_method = billing_objects.payment_method
    two_weeks_ago = (datetime.now(timezone.utc) - timedelta(days=14)).date()
    subscription.start_subscription_cycle(two_weeks_ago)
    subscription_cycle = subscription.subscription_cycle_set.first()

    subscription_cycle.update_usage(subscription.subscription_product_set.first(), 1)

    assert subscription_cycle.price > 0

    subscription_cycle.charge()

    subscription_cycle_charge = subscription_cycle.subscription_cycle_charge_set.first()
    payment_charge = subscription_cycle_charge.payment_charge

    order_history = OrderHistory.create_from_payment_charge(payment_charge)
    assert order_history


def test_billing_contact(db, billing_objects):
    billing_contact = billing_objects.billing_contact
    assert billing_contact.active is False


@pytest.mark.django_db
def test_create_transactions_from_subscription_cycle(charge_objects, billing_objects):
    subscription_cycle = charge_objects["subscription_cycle"]
    charge_objects["subscription"]

    assert (
        OrderLine.objects.count()
        == subscription_cycle.subscription_cycle_product_set.count()
    )
    assert (
        InvoiceLine.objects.count()
        == subscription_cycle.subscription_cycle_product_set.count()
    )


@pytest.mark.django_db
def test_create_transactions_from_product(billing_objects):
    product = billing_objects.product
    product.create_transactions(billing_objects.org)

    assert InvoiceLine.objects.count() == 1
    assert OrderLine.objects.count() == 1
    assert Payment.objects.count() == 1


# New billing-ledger models


@pytest.mark.django_db
def test_order_init(order, billing_objects):
    assert order.org == billing_objects.org
    assert order.amount == 1200.99
    assert order.currency == "USD"
    assert type(order.transaction_id) == uuid.UUID

    assert order.product == billing_objects.product
    assert order.description == "This product is helpful"
    assert order.order_number == 132


@pytest.mark.django_db
def test_invoice_init(invoice, billing_objects):
    assert invoice.org == billing_objects.org
    assert invoice.amount == 1200.99
    assert invoice.currency == "USD"
    assert type(invoice.transaction_id) == uuid.UUID

    assert invoice.subscription == billing_objects.monthly_subscription
    assert invoice.description == "This subscription is helpful"
    assert invoice.invoice_number == 312


@pytest.mark.django_db
def test_payment_init(payment, billing_objects):
    assert payment.invoice_number == 1231
    assert payment.billing_contact == billing_objects.billing_contact
    assert payment.payment_method == billing_objects.payment_method


@pytest.mark.django_db
def test_deposit_init(deposit, billing_objects):
    assert deposit.billing_contact == billing_objects.billing_contact
    assert deposit.payment_method == billing_objects.payment_method


@pytest.mark.django_db
def test_withdrawal_init(withdrawal, billing_objects):
    assert withdrawal.billing_contact == billing_objects.billing_contact
    assert withdrawal.payment_method == billing_objects.payment_method


@pytest.mark.django_db
def test_ledger_init(ledger):
    assert (
        Ledger.objects.filter(
            content_type=ContentType.objects.get_for_model(Withdrawal)
        ).count()
        == 1
    )

    assert (
        Ledger.objects.filter(
            content_type=ContentType.objects.get_for_model(OrderLine)
        ).count()
        == 1
    )

    assert (
        Ledger.objects.filter(
            content_type=ContentType.objects.get_for_model(InvoiceLine)
        ).count()
        == 1
    )


@pytest.mark.django_db
def test_billing_contact_hard_delete(billing_objects):
    # not tied to any transactions so this should run without error
    billing_objects.billing_contact.delete()

    # test that object is deleted
    assert billing_objects.billing_contact.id is None


@pytest.mark.django_db
def test_billing_contact_hard_delete_failure(billing_objects, ledger):
    billing_objects.billing_contact.delete()

    # test that object is soft-deleted
    assert billing_objects.billing_contact.id is not None
    assert billing_objects.billing_contact.status == "deleted"


@pytest.mark.django_db
def test_invoice_number_from_payment_charge(db, billing_objects, mocker):
    """
    Test that invoice number is retrieved from payment charge's invoice.
    """
    # Overrides creating the charge on Stripe's end.
    mocker.patch(
        "billing.payment_processors.stripe.stripe.PaymentIntent.create",
        return_value={"id": 1234, "receipt_url": "https://example.com"},
    )
    subscription = billing_objects.monthly_subscription
    subscription.payment_method = billing_objects.payment_method
    two_weeks_ago = (datetime.now(timezone.utc) - timedelta(days=14)).date()
    subscription.start_subscription_cycle(two_weeks_ago)
    subscription_cycle = subscription.subscription_cycle_set.first()

    subscription_cycle.update_usage(subscription.subscription_product_set.first(), 1)
    
    # Charge the subscription cycle which creates orders and invoice
    subscription_cycle.charge()
    
    # Get the subscription cycle charge
    subscription_cycle_charge = subscription_cycle.subscription_cycle_charge_set.first()
    payment_charge = subscription_cycle_charge.payment_charge
    
    # Verify invoice number is retrieved from payment charge's invoice
    assert subscription_cycle_charge.invoice_number is not None
    assert subscription_cycle_charge.invoice_number == payment_charge.invoice.invoice_number
