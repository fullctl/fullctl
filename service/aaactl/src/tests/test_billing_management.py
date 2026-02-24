# test billing subscription manager
import io
import json
import os
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

STRIPE_CARD_ERROR = "CardError(message='The zip code you supplied failed validation.', param='address_zip', code='incorrect_zip', http_status=402, request_id='req_nVPxvQvGIjDtHe')"


def stripe_mock_data():
    """
    loads stripe mock data from data/billing/stripe_mock_data.json
    """

    file_path = os.path.join(
        os.path.dirname(__file__), "data/billing/stripe_mock_data.json"
    )

    with open(file_path) as f:
        mock_data_dict = json.load(f)

    return mock_data_dict


@pytest.fixture
def mock_stripe():
    """
    Mock the Stripe class.
    """

    mock_data_dict = stripe_mock_data()

    # create patches from keys
    patches = {}
    for key in mock_data_dict.keys():
        patches[key] = patch(key)

    # Start patching and set mock configurations
    mocks = {key: patcher.start() for key, patcher in patches.items()}

    # load mock data and apply to mock return value by key
    for key, value in mock_data_dict.items():
        mocks[key].return_value = value

    yield mocks  # This value will be injected into test functions

    # Stop patching
    for patcher in patches.values():
        patcher.stop()


def assert_no_charge():
    out = io.StringIO()
    call_command("billing_cycles", commit=True, stdout=out)

    output = out.getvalue()

    assert "-- charging " not in output


def assert_retrying_charge():
    out = io.StringIO()
    call_command("billing_cycles", commit=True, stdout=out)

    output = out.getvalue()

    assert "-- retrying failed subscription cycle charge" in output


def assert_no_retrying_charge():
    out = io.StringIO()
    call_command("billing_cycles", commit=True, stdout=out)

    output = out.getvalue()

    assert "-- retrying failed subscription cycle charge" not in output


def run_billing_cycle_with_cutover(_billing_objects) -> dict:
    """
    Run the billing cycle command twice

    This will back-date the billing cycle and then run the command again in order
    to simulate a cut over from the old billing cycle to the new one.

    Returns a dict with the output of the command and the old and new billing cycles
    """

    call_command("billing_cycles", commit=True)

    assert _billing_objects.monthly_subscription.subscription_cycle is not None

    # first billing cycle created, now back-date it, by shifting both `start`
    # and `end` back a month

    billing_cycle = _billing_objects.monthly_subscription.subscription_cycle

    billing_cycle.start = billing_cycle.start - timezone.timedelta(days=32)
    billing_cycle.end = billing_cycle.end - timezone.timedelta(days=32)
    billing_cycle.save()

    # now run the billing_cycles command again, and check that the billing cycle has
    # processed payment and a new billing cycle has been created

    out = io.StringIO()
    err = io.StringIO()
    call_command("billing_cycles", commit=True, stdout=out, stderr=err)

    assert _billing_objects.monthly_subscription.subscription_cycle is not None
    assert _billing_objects.monthly_subscription.subscription_cycle != billing_cycle

    return {
        "stdout": out.getvalue(),
        "stderr": err.getvalue(),
        "billing_cycle": billing_cycle,
        "new_billing_cycle": _billing_objects.monthly_subscription.subscription_cycle,
    }


@pytest.mark.django_db
def test_new_billing_cycle_creation(billing_objects, mock_stripe):
    """
    Test that a new billing cycle is created
    """
    # Call the billing_cycles command and capture output

    call_command("billing_cycles", commit=True)
    assert billing_objects.monthly_subscription.subscription_cycle is not None


@pytest.mark.django_db
def test_billing_cycle_progression(billing_objects_w_pay, mock_stripe):
    """
    Test that a billing cycle is progressed
    """

    result = run_billing_cycle_with_cutover(billing_objects_w_pay)

    billing_cycle = result["billing_cycle"]
    new_billing_cycle = result["new_billing_cycle"]

    # check new billing cycle is started
    assert not new_billing_cycle.ended
    assert not new_billing_cycle.charged

    # check old cycle has been processed
    assert billing_cycle.charged

    cycle_charge = billing_cycle.subscription_cycle_charge_set.first()
    payment_charge = cycle_charge.payment_charge

    assert cycle_charge.invoice_number
    assert payment_charge.invoice_number
    assert payment_charge.order_number

    assert float(payment_charge.price) == 125.99

    # refresh to ensure we have latest DB values
    billing_cycle.refresh_from_db()

    # cycle should now be marked as paid
    assert billing_cycle.status == "paid"

    # Persisted Order & Invoice relations should be set on the cycle and match
    assert billing_cycle.invoice is not None
    assert billing_cycle.order is not None

    # Invoice number on cycle charge / payment charge matches persisted invoice
    assert billing_cycle.invoice.invoice_number == cycle_charge.invoice_number
    assert billing_cycle.invoice.invoice_number == payment_charge.invoice_number

    # ensure base keys match
    expected_base = {
        "processor_txn_id": "pi_1F7J1e2eZvKYlo2C7qX9QZ1c",
        "stripe_payment_intent": "pi_1F7J1e2eZvKYlo2C7qX9QZ1c",
        "receipt_url": "https://pay.stripe.com/receipts/acct_1032D82eZvKYlo2C/ch_4fdAW5ftNQow1a/rcpt_4fdAW5ftNQow1a",
    }

    # ensure base keys match
    for k, v in expected_base.items():
        assert payment_charge.data[k] == v

    # idempotency key should also be present
    assert "idemp_key" in payment_charge.data

    # assert idempotency
    assert_no_charge()


@pytest.mark.django_db
def test_billing_cycle_progression_stripe_failure(billing_objects_w_pay, mock_stripe):
    """
    Test proper handling of Stripe failure when billing cycle is progressed
    """

    mock_stripe["stripe.PaymentIntent.create"].side_effect = Exception("Stripe error")

    result = run_billing_cycle_with_cutover(billing_objects_w_pay)

    billing_cycle = result["billing_cycle"]
    new_billing_cycle = result["new_billing_cycle"]
    cycle_charge = billing_cycle.subscription_cycle_charge_set.first()
    payment_charge = cycle_charge.payment_charge

    assert not new_billing_cycle.ended
    assert not new_billing_cycle.charged
    assert not billing_cycle.charged
    assert billing_cycle.ended

    # The payment charge should be set to failed from the exception
    assert payment_charge.status == "failed"

    billing_cycle.refresh_from_db()

    # subscription cycle status should reflect failed as well
    assert billing_cycle.status == "failed"

    assert payment_charge.failure_notified

    # assert that next time will retry charge
    assert_retrying_charge()


@pytest.mark.django_db
def test_billing_cycle_paused_billing(billing_objects_w_pay, mock_stripe):
    """
    Test that billing cycles are processed but not charged when billing_paused=True
    """
    # Set billing_paused on the subscription
    billing_objects_w_pay.monthly_subscription.billing_paused = True
    billing_objects_w_pay.monthly_subscription.save()

    result = run_billing_cycle_with_cutover(billing_objects_w_pay)

    billing_cycle = result["billing_cycle"]
    new_billing_cycle = result["new_billing_cycle"]

    # Check that the old cycle is ended but not charged
    assert billing_cycle.ended
    assert not billing_cycle.charged

    # Verify new cycle was still created
    assert new_billing_cycle is not None
    assert not new_billing_cycle.ended
    assert not new_billing_cycle.charged

    # Check that output contains message about billing being paused
    assert "billing paused" in result["stdout"].lower()

    # Assert no charges were attempted
    assert_no_charge()


@pytest.mark.django_db
def test_billing_cycle_critical_errors(billing_objects_w_pay, mock_stripe):
    """
    Test proper handling of Stripe failure when billing cycle is progressed
    """

    # we need to patch subscription_cycle_charge.payment_charge.sync_status
    # to raise an exception

    with patch("billing.models.PaymentCharge.sync_status") as mock_sync_status:
        mock_sync_status.side_effect = Exception("Critical error")

        with pytest.raises(Exception) as excinfo:
            result = run_billing_cycle_with_cutover(billing_objects_w_pay)

            # assert "Critical errors occurred" in str(excinfo.value)
            assert excinfo.match("Critical error")

            billing_cycle = result["billing_cycle"]
            new_billing_cycle = result["new_billing_cycle"]
            cycle_charge = billing_cycle.subscription_cycle_charge_set.first()
            payment_charge = cycle_charge.payment_charge

            assert not new_billing_cycle.ended
            assert not new_billing_cycle.charged
            assert not billing_cycle.charged
            assert billing_cycle.ended

            billing_cycle.refresh_from_db()

            assert billing_cycle.status == "error"
            assert new_billing_cycle.status == "open"

            # assert that next time will not retry charge
            assert_no_retrying_charge()


@pytest.mark.django_db
def test_billing_cycle_progression_with_pending_charge(
    billing_objects_w_pay, mock_stripe
):
    """
    Test that a new charge is not created if one is already pending.
    """

    # mock stripe to return a pending status
    mock_stripe["stripe.PaymentIntent.create"].return_value = {
        "id": "pi_pending_123",
        "status": "requires_action",
    }
    mock_stripe["stripe.PaymentIntent.retrieve"].return_value = {
        "id": "pi_pending_123",
        "status": "requires_action",
    }

    # run billing cycle to create a pending charge
    result = run_billing_cycle_with_cutover(billing_objects_w_pay)

    billing_cycle = result["billing_cycle"]
    cycle_charge = billing_cycle.subscription_cycle_charge_set.first()

    assert cycle_charge is not None
    assert cycle_charge.payment_charge.status == "pending"

    # check that cycle.charged sees the pending charge
    assert billing_cycle.charged is True

    # run billing again, no new charge should be made
    assert_no_charge()


@pytest.mark.django_db
def test_idempotency_on_charge_retry(billing_objects_w_pay, mock_stripe):
    """
    Test that on charge retry, the idempotency key is passed to stripe.
    """
    # 1. Fail the first charge attempt
    mock_stripe["stripe.PaymentIntent.create"].side_effect = Exception("Stripe error")
    try:
        run_billing_cycle_with_cutover(billing_objects_w_pay)
    except CommandError:
        # Expected to fail on the first run
        pass

    billing_cycle = (
        billing_objects_w_pay.monthly_subscription.subscription_cycle_set.first()
    )
    # check that it failed
    assert not billing_cycle.charged
    first_cycle_charge = billing_cycle.subscription_cycle_charge_set.first()
    assert first_cycle_charge.payment_charge.status == "failed"

    # 2. Reset mock to succeed on retry and assert retrying
    mock_stripe["stripe.PaymentIntent.create"].side_effect = None
    mock_stripe["stripe.PaymentIntent.create"].return_value = stripe_mock_data()[
        "stripe.PaymentIntent.create"
    ]
    assert_retrying_charge()

    # check idempotency key is present in payment charge data again
    billing_cycle.refresh_from_db()
    second_cycle_charge = billing_cycle.subscription_cycle_charge_set.first()
    payment_charge = second_cycle_charge.payment_charge
    assert payment_charge.status == "ok"
    assert "idemp_key" in payment_charge.data


@pytest.mark.django_db
def test_duplicate_subscription_cycle_charge_constraint(billing_objects_w_pay):
    """
    Test that the unique constraint on SubscriptionCycleCharge prevents duplicates.
    """
    from billing.models import PaymentCharge, SubscriptionCycleCharge
    from django.db import IntegrityError

    # run billing cycle to create a cycle
    call_command("billing_cycles", commit=True)
    cycle = billing_objects_w_pay.monthly_subscription.subscription_cycle
    assert cycle is not None

    # backdate it to make it chargeable
    cycle.start = cycle.start - timezone.timedelta(days=32)
    cycle.end = cycle.end - timezone.timedelta(days=32)
    cycle.save()

    # run billing_cycles to create the charge
    call_command("billing_cycles", commit=True)

    charge1 = cycle.subscription_cycle_charge_set.first()
    assert charge1 is not None

    # now try to create another one manually
    payment_charge = PaymentCharge.objects.create(
        payment_method=billing_objects_w_pay.monthly_subscription.payment_method,
        price=cycle.price,
        description="test duplicate",
    )

    with pytest.raises(IntegrityError, match="uniq_cycle_charge"):
        SubscriptionCycleCharge.objects.create(
            subscription_cycle=cycle, payment_charge=payment_charge
        )


@pytest.mark.django_db
def test_invoice_reuse_on_charge_retry(billing_objects_w_pay, mock_stripe):
    """Ensure the same invoice is reused when a cycle charge is retried."""

    # 1. Make Stripe fail so the first charge attempt fails (invoice created)
    mock_stripe["stripe.PaymentIntent.create"].side_effect = Exception("Stripe error")

    try:
        run_billing_cycle_with_cutover(billing_objects_w_pay)
    except CommandError:
        pass

    billing_cycle = (
        billing_objects_w_pay.monthly_subscription.subscription_cycle_set.first()
    )

    first_invoice = billing_cycle.invoice
    assert first_invoice is not None

    # Grab the failed PaymentCharge BEFORE retry so we can compare later
    failed_charge = billing_cycle.subscription_cycle_charge_set.first().payment_charge
    assert first_invoice.charge_object_id == failed_charge.id

    # 2. Reset Stripe mocks so the retry succeeds
    mock_stripe["stripe.PaymentIntent.create"].side_effect = None
    mock_stripe["stripe.PaymentIntent.create"].return_value = stripe_mock_data()[
        "stripe.PaymentIntent.create"
    ]

    # Run billing command again – should retry failed payment
    assert_retrying_charge()

    invoice_id = first_invoice.id
    billing_cycle.refresh_from_db()
    first_invoice.refresh_from_db()

    assert billing_cycle.status == "paid"

    # Invoice relation should still point to the same invoice object
    assert billing_cycle.invoice_id == invoice_id
    new_cycle_charge = billing_cycle.subscription_cycle_charge_set.first()
    assert new_cycle_charge.invoice_number == first_invoice.invoice_number

    new_payment_charge = new_cycle_charge.payment_charge
    # Invoice should now link to the new successful charge
    assert first_invoice.charge_object_id == new_payment_charge.id
    assert new_payment_charge.id != failed_charge.id


@pytest.mark.django_db
def test_invoice_charge_object_updated_on_retry(billing_objects_w_pay, mock_stripe):
    """Failed payment leaves invoice linked to failed charge; retry replaces linkage."""

    # Force failure on first attempt
    mock_stripe["stripe.PaymentIntent.create"].side_effect = Exception("Stripe error")

    try:
        run_billing_cycle_with_cutover(billing_objects_w_pay)
    except CommandError:
        pass

    billing_cycle = (
        billing_objects_w_pay.monthly_subscription.subscription_cycle_set.first()
    )
    invoice = billing_cycle.invoice
    failed_charge = billing_cycle.subscription_cycle_charge_set.first().payment_charge

    assert invoice.charge_object_id == failed_charge.id

    # Succeed on retry
    mock_stripe["stripe.PaymentIntent.create"].side_effect = None
    mock_stripe["stripe.PaymentIntent.create"].return_value = stripe_mock_data()[
        "stripe.PaymentIntent.create"
    ]

    assert_retrying_charge()

    invoice.refresh_from_db()
    billing_cycle.refresh_from_db()

    new_charge = billing_cycle.subscription_cycle_charge_set.first().payment_charge

    # Link should now point to the new PaymentCharge
    assert invoice.charge_object_id == new_charge.id
    assert new_charge.id != failed_charge.id
    # Ensure charge price matches invoice total
    assert float(invoice.price) == float(new_charge.price)


@pytest.mark.django_db
def test_billing_cycles_group_filter(billing_objects_w_pay, mock_stripe):
    """Verify that the --group flag limits processing to the specified ProductGroup."""

    # 1. Create the initial billing cycle (not yet chargeable)
    call_command("billing_cycles", commit=True)

    subscription = billing_objects_w_pay.monthly_subscription
    cycle = subscription.subscription_cycle
    assert cycle is not None

    # 2. Back-date the cycle so it becomes chargeable on next run
    cycle.start = cycle.start - timezone.timedelta(days=32)
    cycle.end = cycle.end - timezone.timedelta(days=32)
    cycle.save()

    # Sanity check – still uncharged
    assert not cycle.charged

    # Helper function to call command and return output
    def run_cmd(**opts):
        out = io.StringIO()
        call_command("billing_cycles", stdout=out, **opts)
        return out.getvalue()

    # 3. Run with an unrelated ProductGroup – expect NO charge
    other_pg_id = billing_objects_w_pay.other_product_group.id
    output_other = run_cmd(commit=True, group=other_pg_id)
    assert "-- charging " not in output_other
    cycle.refresh_from_db()
    assert not cycle.charged

    # 4. Run with the correct ProductGroup – expect a charge to be made
    correct_pg_id = billing_objects_w_pay.product_group.id
    output_correct = run_cmd(commit=True, group=correct_pg_id)
    assert "-- charging " in output_correct
    cycle.refresh_from_db()
    assert cycle.charged


@pytest.mark.django_db
def test_retry_amount_idempotent_after_price_change(billing_objects_w_pay, mock_stripe):
    """If recurring product price changes after a failed attempt, retry bills original amount."""

    # 1. Fail first charge attempt so invoice & failed charge are created
    mock_stripe["stripe.PaymentIntent.create"].side_effect = Exception("Stripe error")

    try:
        run_billing_cycle_with_cutover(billing_objects_w_pay)
    except CommandError:
        # Expected failure path
        pass

    billing_cycle = (
        billing_objects_w_pay.monthly_subscription.subscription_cycle_set.first()
    )
    invoice = billing_cycle.invoice
    assert invoice is not None
    original_total = float(invoice.price)
    assert original_total > 0

    # Capture the recurring product and change its price
    rec_product = billing_objects_w_pay.product_subscription_fixed.recurring_product
    assert float(rec_product.price) == original_total  # sanity (fixed price product)

    rec_product.price = rec_product.price + 50  # bump price
    rec_product.save()

    # 2. Succeed on retry
    mock_stripe["stripe.PaymentIntent.create"].side_effect = None
    mock_stripe["stripe.PaymentIntent.create"].return_value = stripe_mock_data()[
        "stripe.PaymentIntent.create"
    ]

    assert_retrying_charge()

    invoice.refresh_from_db()
    billing_cycle.refresh_from_db()
    cycle_charge = billing_cycle.subscription_cycle_charge_set.first()
    payment_charge = cycle_charge.payment_charge

    # Ensure invoice amount unchanged
    assert float(invoice.price) == original_total
    # PaymentCharge should match invoice amount, not new product price
    assert float(payment_charge.price) == original_total
    # And it should NOT equal the updated product price
    assert float(payment_charge.price) != float(rec_product.price)
