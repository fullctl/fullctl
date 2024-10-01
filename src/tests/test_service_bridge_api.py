import json

import pytest
from django.contrib.auth import authenticate
from django.urls import reverse

import account.models as models
from account.models import Organization
from tests.helpers import assert_expected, strip_api_fields
from whitelabel_fullctl.models import OrganizationBranding


def test_api_select_best_branding(db, account_objects, settings):

    requesting_org = account_objects.other_org

    # set up global branding org

    global_branding_org = Organization.objects.create(
        name="Global Branding Org", slug="global-branding-org"
    )

    global_branding = OrganizationBranding.objects.create(
        org=global_branding_org, css={"color": "red"}
    )

    settings.BRANDING_ORG = "global-branding-org"

    # requesting org has no branding, so should get global branding

    api_url = reverse("service_bridge_api:service-bridge-data-org_branding-list")

    response = account_objects.api_client.get(f"{api_url}?best={requesting_org.slug}")

    assert response.status_code == 200
    data = response.json()

    assert len(data["data"]) == 1
    assert data["data"][0]["org"] == global_branding_org.id
    assert data["data"][0]["css"] == {"color": "red"}

    # create branding for requesting org

    requesting_org_branding = OrganizationBranding.objects.create(
        org=requesting_org, css={"color": "blue"}
    )

    # now requesting org should get its own branding

    response = account_objects.api_client.get(f"{api_url}?best={requesting_org.slug}")

    assert response.status_code == 200
    data = response.json()

    assert len(data["data"]) == 1
    assert data["data"][0]["org"] == requesting_org.id
    assert data["data"][0]["css"] == {"color": "blue"}

    # delete global branding

    global_branding.delete()

    # now requesting org should still get its own branding

    response = account_objects.api_client.get(f"{api_url}?best={requesting_org.slug}")

    assert response.status_code == 200
    data = response.json()

    assert len(data["data"]) == 1
    assert data["data"][0]["org"] == requesting_org.id
    assert data["data"][0]["css"] == {"color": "blue"}

    # Delete requesting org branding

    requesting_org_branding.delete()

    # no more brandings left, BRANDING_ORG still set, no branding should be returned

    response = account_objects.api_client.get(f"{api_url}?best={requesting_org.slug}")

    assert response.status_code == 200
    data = response.json()

    assert len(data["data"]) == 0

    # unset BRANDING_ORG, no branding should be returned

    settings.BRANDING_ORG = None

    response = account_objects.api_client.get(f"{api_url}?best={requesting_org.slug}")

    assert response.status_code == 200
    data = response.json()

    assert len(data["data"]) == 0
