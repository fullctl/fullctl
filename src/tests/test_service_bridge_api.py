from django.urls import reverse

import django_devicectl.models as models


def test_get_vlan(db, account_objects):
    client = account_objects.api_client
    facility = account_objects.facility

    vlan = models.Vlan(
        instance=account_objects.devicectl_instance,
        facility=facility,
        name="Test Vlan",
        vlan=12,
        slug="test_vlan",
        description="Sample Vlan test",
    )
    vlan.save()

    api_url = reverse("service_bridge_api:service-bridge-data-vlan-list")
    response = client.get(f"{api_url}?id={vlan.id}")

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["name"] == vlan.name
    assert data["data"][0]["slug"] == vlan.slug
    assert data["data"][0]["description"] == vlan.description
    assert data["data"][0]["facility_name"] == facility.name
    assert data["data"][0]["facility_slug"] == facility.slug


def test_get_vlan_by_org(db, account_objects):
    client = account_objects.api_client
    org = account_objects.org
    facility = account_objects.facility

    vlan = models.Vlan(
        instance=account_objects.devicectl_instance,
        facility=facility,
        name="Test Vlan",
        vlan=12,
        slug="test_vlan",
        description="Sample Vlan test",
    )
    vlan.save()

    api_url = reverse("service_bridge_api:service-bridge-data-vlan-list")
    response = client.get(f"{api_url}?org_slug={org.slug}")

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["name"] == vlan.name
    assert data["data"][0]["slug"] == vlan.slug
    assert data["data"][0]["description"] == vlan.description
    assert data["data"][0]["facility_name"] == facility.name
    assert data["data"][0]["facility_slug"] == facility.slug
