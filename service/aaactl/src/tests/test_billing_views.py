import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_order_history_details(client_anon, billing_objects, charge_objects):
    order_item_id = charge_objects["order_history"].order_id

    # Test anon
    anon_response = client_anon.get(
        reverse("billing:order-history-details", args=[order_item_id])
        + f"?org={billing_objects.org.slug}"
    )
    assert anon_response.status_code == 302

    # Test non-existing order history item
    response = billing_objects.client.get(
        reverse("billing:order-history-details", args=[100])
        + f"?org={billing_objects.org.slug}"
    )
    assert response.status_code == 404

    response = billing_objects.client.get(
        reverse("billing:order-history-details", args=[order_item_id])
        + f"?org={billing_objects.org.slug}"
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_billing_contacts(client_anon, billing_objects):
    anon_response = client_anon.get(reverse("billing:billing-contacts"))
    assert anon_response.status_code == 302

    response = billing_objects.client.get(
        reverse("billing:billing-contacts") + f"?org={billing_objects.org.slug}"
    )
    assert response.status_code == 200
    assert billing_objects.billing_contact.name in str(response.content)


@pytest.mark.django_db
def test_services(client_anon, billing_objects):
    anon_response = client_anon.get(reverse("billing:services"))
    assert anon_response.status_code == 302

    response = billing_objects.client.get(
        reverse("billing:services") + f"?org={billing_objects.org.slug}"
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_setup(client_anon, billing_objects):
    anon_response = client_anon.get(reverse("billing:setup"))
    assert anon_response.status_code == 302

    response = billing_objects.client.get(
        reverse("billing:setup") + f"?org={billing_objects.org.slug}"
    )
    assert response.status_code == 200


@pytest.mark.django_db
def test_setup_billing_contact_prepop(billing_objects):
    response = billing_objects.client.get(
        reverse("billing:setup")
        + f"?billing_contact={billing_objects.billing_contact.id}"
        + "&"
        + f"org={billing_objects.org.slug}"
    )
    assert response.status_code == 200
    assert billing_objects.billing_contact.name in response.content.decode("utf-8")
