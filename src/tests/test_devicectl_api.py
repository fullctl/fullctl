import json

import pytest
from django.urls import reverse

import django_devicectl.models as models


def test_create_vlan(db, account_objects):
    client = account_objects.api_client
    facility = account_objects.facility
    org = account_objects.org

    response = client.post(
        reverse("devicectl_api:vlan-list", args=(org.slug,)),
        json.dumps(
            {
                "facility": facility.id,
                "name": "Test Vlan",
                "vlan": 12,
                "slug": "test_vlan",
                "description": "Sample Vlan test",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["facility_name"] == facility.name
    assert data[0]["facility_slug"] == facility.slug
    assert models.Vlan.objects.get(id=data[0]["id"])


def test_retrieve_vlan(db, account_objects):
    client = account_objects.api_client
    org = account_objects.org
    facility = account_objects.facility

    vlan = models.Vlan(
        instance=account_objects.devicectl_instance,
        facility=account_objects.facility,
        name="Test Vlan",
        vlan=12,
        slug="test_vlan",
        description="Sample Vlan test",
    )
    vlan.save()

    response = client.get(
        reverse(
            "devicectl_api:vlan-detail",
            args=(org.slug, vlan.id),
        ),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == vlan.name
    assert data[0]["slug"] == vlan.slug
    assert data[0]["description"] == vlan.description
    assert data[0]["facility_name"] == facility.name
    assert data[0]["facility_slug"] == facility.slug
    assert models.Vlan.objects.get(id=data[0]["id"])


def test_list_vlans(db, account_objects):
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

    response = client.get(
        reverse(
            "devicectl_api:vlan-list",
            args=(org.slug,),
        ),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == vlan.name
    assert data[0]["slug"] == vlan.slug
    assert data[0]["description"] == vlan.description
    assert data[0]["facility_name"] == facility.name
    assert data[0]["facility_slug"] == facility.slug
    assert models.Vlan.objects.get(id=data[0]["id"])


def test_delete_vlan(db, account_objects):
    client = account_objects.api_client
    org = account_objects.org

    vlan = models.Vlan(
        instance=account_objects.devicectl_instance,
        facility=account_objects.facility,
        name="Test Vlan",
        vlan=12,
        slug="test_vlan",
        description="Sample Vlan test",
    )
    vlan.save()

    response = client.delete(
        reverse(
            "devicectl_api:vlan-detail",
            args=(org.slug, vlan.id),
        ),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1

    with pytest.raises(models.Vlan.DoesNotExist):
        models.Vlan.objects.get(id=data[0]["id"])


def test_facility_list_vlans(db, account_objects):
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

    response = client.get(
        reverse(
            "devicectl_api:facility-vlans",
            args=(
                org.slug,
                facility.slug,
            ),
        ),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == vlan.name
    assert data[0]["slug"] == vlan.slug
    assert data[0]["description"] == vlan.description
    assert data[0]["facility_name"] == facility.name
    assert data[0]["facility_slug"] == facility.slug
    assert models.Vlan.objects.get(id=data[0]["id"])
