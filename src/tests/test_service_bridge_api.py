import json

from django.urls import reverse

import account.models as models
from account.models import Organization
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


def test_api_select_poc(db, account_objects, settings):
    delivery_type = "email"
    service = "ixctl"
    status = "ok"
    config = {"services": [service], "recipients": ["test@test.com", "email@email.com"]}
    _type = "notifications"
    poc = models.PointOfContact(
        org=account_objects.org, delivery_type=delivery_type, config=config
    )
    poc.save()

    api_url = reverse("service_bridge_api:service-bridge-data-poc-list")

    response = account_objects.api_client.get(f"{api_url}?service={service}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["org"] == account_objects.org.id
    assert data["data"][0]["config"] == config
    assert data["data"][0]["status"] == "ok"

    response = account_objects.api_client.get(f"{api_url}?status={status}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["org"] == account_objects.org.id
    assert data["data"][0]["config"] == config
    assert data["data"][0]["status"] == status

    response = account_objects.api_client.get(
        f"{api_url}?delivery_type={delivery_type}"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1

    response = account_objects.api_client.get(
        f"{api_url}?org={account_objects.org.slug}"
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1

    response = account_objects.api_client.get(f"{api_url}?type={_type}")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1


def test_api_update_poc(db, account_objects):
    poc = models.PointOfContact(
        org=account_objects.org,
        config={
            "services": ["ixctl", "peerctl"],
            "recipients": ["test@test.com", "email@email.com"],
        },
    )
    poc.save()

    api_url = reverse("service_bridge_api:service-bridge-data-poc-list")
    response = account_objects.api_client.get(f"{api_url}?status=ok")

    assert response.status_code == 200
    data = response.json()
    poc_id = data["data"][0]["id"]
    org_id = data["data"][0]["org"]

    config = {"services": None, "recipients": ["test@test.com"]}
    put_api_url = reverse(
        "service_bridge_api:service-bridge-data-poc-detail", args=(poc_id,)
    )
    response = account_objects.api_client.put(
        put_api_url,
        data=json.dumps(
            {
                "org": org_id,
                "config": config,
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()
    assert data["data"][0]["config"] == config


def test_api_create_poc(db, account_objects, settings):
    api_url = reverse("service_bridge_api:service-bridge-data-poc-list")

    config = {"services": ["ixctl"], "recipients": ["test@test.com", "email@email.com"]}
    response = account_objects.api_client.post(
        api_url,
        data=json.dumps(
            {
                "org": account_objects.org.id,
                "delivery_type": "email",
                "service": "ixctl",
                "status": "ok",
                "config": config,
                "type": "notifications",
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["org"] == account_objects.org.id
    assert data["data"][0]["config"] == config
    assert data["data"][0]["status"] == "ok"
