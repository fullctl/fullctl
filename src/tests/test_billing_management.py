# test billing subscription manager
import io
import json
import os
from unittest.mock import patch

import pytest
from django.core.management import call_command
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
    assert payment_charge.data == {
        "processor_txn_id": "pi_1F7J1e2eZvKYlo2C7qX9QZ1c",
        "stripe_payment_intent": "pi_1F7J1e2eZvKYlo2C7qX9QZ1c",
        "receipt_url": "https://pay.stripe.com/receipts/acct_1032D82eZvKYlo2C/ch_4fdAW5ftNQow1a/rcpt_4fdAW5ftNQow1a",
    }

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

            assert billing_cycle.status == "error"
            assert new_billing_cycle.status == "open"

            # assert that next time will not retry charge
            assert_no_retrying_charge()
