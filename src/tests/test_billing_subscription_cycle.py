import pytest
from django.utils import timezone

from account.models import Organization
from billing.models import (
    ProductGroup,
    Subscription,
    SubscriptionCycle,
    BillingContact,
    PaymentMethod,
    PaymentCharge,
    SubscriptionCycleCharge,
)


@pytest.mark.django_db
def test_subscription_cycle_charged_pending():
    """SubscriptionCycle.charged() should return True when a pending charge exists."""

    # Minimal business objects
    org = Organization.objects.create(name="Test Org")
    group = ProductGroup.objects.create(name="Test Group")
    subscription = Subscription.objects.create(
        org=org,
        group=group,
        subscription_cycle_start=timezone.now(),
    )

    today = timezone.now().date()
    cycle = SubscriptionCycle.objects.create(
        subscription=subscription, start=today, end=today
    )

    # Billing contact + payment method (required by PaymentCharge)
    billing_contact = BillingContact.objects.create(
        org=org,
        name="Tester",
        email="tester@example.com",
        status="ok",
    )

    payment_method = PaymentMethod.objects.create(
        billing_contact=billing_contact,
        processor="stripe",
        holder="Tester",
        country="US",
        city="Test City",
        address1="123 Test St",
        postal_code="12345",
        status="ok",
    )

    payment_charge = PaymentCharge.objects.create(
        payment_method=payment_method,
        price=0.0,
        description="Test charge",
        status="pending",
    )

    SubscriptionCycleCharge.objects.create(
        subscription_cycle=cycle, payment_charge=payment_charge
    )

    assert cycle.charged is True 