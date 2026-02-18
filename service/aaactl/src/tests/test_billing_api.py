import pytest
from django.urls import reverse

import billing.models as models
from tests.helpers import strip_api_fields


@pytest.mark.django_db
def test_get_organization(billing_objects):
    response = billing_objects.api_client.get(
        reverse("billing_api:org-detail", args=[billing_objects.org.slug])
    )

    assert response.status_code == 200
    assert response.json()["data"][0] == {}


@pytest.mark.django_db
def test_post_billing_setup(billing_objects, mocker):
    last_4 = billing_objects.payment_method.data["stripe_payment_method"][-4:]
    data = {
        "agreement_tos": True,
        "holder": "George Contact",
        "phone_number_country": "US",
        "phone_number": "604 401 1234",
        "client_secret": "test_secret",
        "setup_intent_id": "test_id",
    }
    output = {
        "agreement_tos": True,
        "payment_method": "George Contact: stripe-3",
        "payment_method_id": 3,
        "holder": "George Contact",
        "phone_number": "+16044011234",
    }
    mocker.patch(
        "billing.payment_processors.stripe.stripe.Customer.create",
        return_value={"id": 1234},
    )
    mocker.patch(
        "billing.payment_processors.stripe.stripe.Customer.create_source",
        return_value={"id": 2345, "last4": last_4},
    )
    mocker.patch(
        "billing.payment_processors.stripe.stripe.Customer.modify_source",
        return_value=None,
    )
    mocker.patch(
        "billing.payment_processors.stripe.stripe.SetupIntent.create",
        return_value={
            "id": 2345,
            "client_secret": "test_secret",
            "status": "succeeded",
        },
    )

    response = billing_objects.api_client.post(
        reverse("billing_api:org-billing-setup", args=[billing_objects.org.slug]),
        data=data,
    )

    print(response.content)

    assert response.status_code == 200
    assert response.json()["data"][0] == output


@pytest.mark.django_db
def test_get_payment_methods(billing_objects, data_billing_api_billing_contact):
    # Cannot access without billing_contact
    response = billing_objects.api_client.get(
        reverse("billing_api:org-payment-methods", args=[billing_objects.org.slug])
    )
    assert response.status_code == 400
    assert "billing_contact" in response.json()["errors"]

    # Can access with billing_contact
    response = billing_objects.api_client.get(
        reverse("billing_api:org-payment-methods", args=[billing_objects.org.slug])
        + f"?billing_contact={billing_objects.billing_contact.id}"
    )
    assert billing_objects.billing_contact.org == billing_objects.org
    print("methods", billing_objects.billing_contact.payment_method_set.all())
    print(response.content)

    assert strip_api_fields(response.json()) == strip_api_fields(
        data_billing_api_billing_contact.expected
    )


@pytest.mark.django_db
def test_delete_payment_methods(billing_objects):
    input_data = {
        "custom_name": "Test Customer 2",
        "holder": "George Contact",
        "country": "US",
        "city": "Chicago",
        "address1": "5400 Test Ave",
        "postal_code": "60660",
        "state": "IL",
    }

    new_payment_method = models.PaymentMethod.objects.create(
        billing_contact=billing_objects.billing_contact,
        data={"stripe_payment_method": "1200828282828210"},
        status="ok",
        **input_data,
    )

    input_data["id"] = new_payment_method.id
    input_data["billing_contact"] = billing_objects.billing_contact.id

    response = billing_objects.api_client.delete(
        reverse("billing_api:org-payment-method", args=[billing_objects.org.slug]),
        data=input_data,
    )

    output_data = response.json()["data"][0]
    assert response.status_code == 200
    assert set(input_data.items()).issubset(set(output_data.items()))
    assert models.PaymentMethod.objects.count() == 1


@pytest.mark.django_db
def test_update_billing_contact(billing_objects):
    url = reverse("billing_api:org-billing-contact", args=[billing_objects.org.slug])
    data = {
        "id": billing_objects.billing_contact.id,
        "org": billing_objects.billing_contact.org,
        "name": billing_objects.billing_contact.name,
        "email": "newemail@fullctl.com",
        "phone_number": "+16044011234",
        "phone_number_country": "US",
    }
    response = billing_objects.api_client.put(url, data=data)
    assert response.status_code == 200
    assert models.BillingContact.objects.first().email == "newemail@fullctl.com"

    # Test incomplete information
    del data["email"]
    response = billing_objects.api_client.put(url, data=data)
    assert response.status_code == 400


@pytest.mark.django_db
def test_delete_billing_contact(billing_objects):
    """
    Billing contact not tied to any transactions, hard delete possible
    """

    url = reverse("billing_api:org-billing-contact", args=[billing_objects.org.slug])
    data = {
        "id": billing_objects.billing_contact.id,
        "org": billing_objects.billing_contact.org,
        "name": billing_objects.billing_contact.name,
        "email": "newemail@localhost",
    }
    response = billing_objects.api_client.delete(url, data=data)
    assert response.status_code == 200
    assert models.BillingContact.objects.count() == 0


@pytest.mark.django_db
def test_delete_billing_contact_soft(billing_objects, ledger):
    """
    Billing contact tied to transactions, soft delete only
    """
    url = reverse("billing_api:org-billing-contact", args=[billing_objects.org.slug])
    data = {
        "id": billing_objects.billing_contact.id,
        "org": billing_objects.billing_contact.org,
        "name": billing_objects.billing_contact.name,
        "email": "newemail@localhost",
    }
    response = billing_objects.api_client.delete(url, data=data)
    assert response.status_code == 200
    assert models.BillingContact.objects.count() == 1
    assert models.BillingContact.objects.first().status == "deleted"


@pytest.mark.django_db
def test_delete_active_billing_contact(billing_objects):
    # Connect payment method to subscription, ie make billing contact active
    subscription = billing_objects.monthly_subscription
    subscription.payment_method = billing_objects.payment_method
    subscription.save()
    assert billing_objects.billing_contact.active

    url = reverse("billing_api:org-billing-contact", args=[billing_objects.org.slug])
    data = {
        "id": billing_objects.billing_contact.id,
        "org": billing_objects.billing_contact.org,
        "name": billing_objects.billing_contact.name,
        "email": "newemail@localhost",
    }

    response = billing_objects.api_client.delete(url, data=data)
    assert response.status_code == 200
    assert models.BillingContact.objects.count() == 0


@pytest.mark.django_db
def test_get_services(billing_objects, data_billing_api_subscriptions):
    response = billing_objects.api_client.get(
        reverse("billing_api:org-services", args=[billing_objects.org.slug])
    )
    assert strip_api_fields(response.json()) == strip_api_fields(
        data_billing_api_subscriptions.expected
    )


@pytest.mark.django_db
def test_get_orders(billing_objects, charge_objects):
    response = billing_objects.api_client.get(
        reverse("billing_api:org-orders", args=[billing_objects.org.slug])
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_get_products(billing_objects, data_billing_api_product):
    response = billing_objects.api_client.get(reverse("billing_api:product-list"))
    assert response.status_code == 200
    assert strip_api_fields(response.json()) == strip_api_fields(
        data_billing_api_product.expected
    )
