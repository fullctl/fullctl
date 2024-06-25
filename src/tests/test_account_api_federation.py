import json

from django.contrib.auth import authenticate
from django.urls import reverse

import account.models as models
import account.models.federation as federation_models
from tests.helpers import assert_expected, strip_api_fields


def test_federated_service_urls_list(db, account_objects):
    """
    Tests listing federated service URLs for an organization
    """

    auth_info = federation_models.AuthFederation.create_for_org(
        account_objects.org, user=account_objects.user
    )

    service_id = account_objects.federated_service_support.id

    # Create a test federated service URL for the organization
    test_url = "https://example.com/federated-service"
    account_objects.api_client.post(
        reverse(
            "account_api:org-add-federated-service-url",
            args=(account_objects.org.slug,),
        ),
        data=json.dumps({"url": test_url, "service": service_id}),
        content_type="application/json",
    )

    response = account_objects.api_client.get(
        reverse(
            "account_api:org-federated-service-urls", args=(account_objects.org.slug,)
        )
    )

    assert response.status_code == 200

    result = response.json()["data"]

    assert len(result) == 1

    url = result[0]

    assert url["url"] == test_url
    assert url["service"] == service_id
    assert url["auth"] == auth_info.auth.id

    # assert redirect url set on auth_info.auth
    auth_info.auth.refresh_from_db()
    assert auth_info.auth.application.redirect_uris == f"{test_url}/complete/twentyc/"

    # test unauthenticated user
    response = account_objects.api_client_anon.get(
        reverse(
            "account_api:org-federated-service-urls", args=(account_objects.org.slug,)
        )
    )

    assert response.status_code == 403


def test_federated_service_url_create(db, account_objects):
    """
    Tests creating a new federated service URL for an organization
    """

    federation_models.AuthFederation.create_for_org(
        account_objects.org, user=account_objects.user
    )

    service_id = account_objects.federated_service_support.id

    test_url = "https://example.com/new-federated-service"
    response = account_objects.api_client.post(
        reverse(
            "account_api:org-add-federated-service-url",
            args=(account_objects.org.slug,),
        ),
        data=json.dumps({"url": test_url, "service": service_id}),
        content_type="application/json",
    )

    assert response.status_code == 200

    result = response.json()["data"][0]

    assert result["url"] == test_url
    assert result["service"] == service_id

    # test that calling create again with the same service errors with 400 Bad request

    response = account_objects.api_client.post(
        reverse(
            "account_api:org-add-federated-service-url",
            args=(account_objects.org.slug,),
        ),
        data=json.dumps({"url": test_url, "service": service_id}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["errors"]["non_field_errors"] == [
        "Service URL for this service already exists."
    ]

    # test unauthenticated user
    response = account_objects.api_client_anon.post(
        reverse(
            "account_api:org-add-federated-service-url",
            args=(account_objects.org.slug,),
        ),
        data=json.dumps({"url": test_url, "service": service_id}),
        content_type="application/json",
    )

    assert response.status_code == 403


def test_federated_service_url_update(db, account_objects):
    """
    Tests updating a federated service URL for an organization
    """

    auth_info = federation_models.AuthFederation.create_for_org(
        account_objects.org, user=account_objects.user
    )

    service_id = account_objects.federated_service_support.id

    # Create a test federated service URL for the organization
    test_url = "https://example.com/federated-service"
    account_objects.api_client.post(
        reverse(
            "account_api:org-add-federated-service-url",
            args=(account_objects.org.slug,),
        ),
        data=json.dumps({"url": test_url, "service": service_id}),
        content_type="application/json",
    )

    # load the url
    url_object = federation_models.FederatedServiceURL.objects.get(url=test_url)

    # Update the URL
    new_url = "https://example.com/new-federated-service"
    response = account_objects.api_client.put(
        reverse(
            "account_api:org-update-federated-service-url",
            args=(account_objects.org.slug, url_object.id),
        ),
        data=json.dumps({"url": new_url, "service": service_id}),
        content_type="application/json",
    )

    assert response.status_code == 200

    result = response.json()["data"][0]

    assert result["url"] == new_url
    assert result["service"] == service_id

    # assert redirect url set on auth_info.auth
    auth_info.auth.refresh_from_db()
    assert auth_info.auth.application.redirect_uris == f"{new_url}/complete/twentyc/"

    # test unauthenticated user
    response = account_objects.api_client_anon.put(
        reverse(
            "account_api:org-update-federated-service-url",
            args=(account_objects.org.slug, url_object.id),
        ),
        data=json.dumps({"url": new_url, "service": service_id}),
        content_type="application/json",
    )

    assert response.status_code == 403


def test_federated_auth_retrieve(db, account_objects):
    """
    Tests retrieving AuthFederation details for an organization.
    """
    # First, create a federated auth for the org to retrieve later
    auth_info = federation_models.AuthFederation.create_for_org(
        account_objects.org, user=account_objects.user
    )

    response = account_objects.api_client.get(
        reverse("account_api:org-federated-auth", args=(account_objects.org.slug,))
    )

    assert response.status_code == 200
    result = response.json()["data"][0]
    assert result["id"] == auth_info.auth.id
    assert result["org"] == account_objects.org.id
    assert "client_id" in result
    assert "client_secret" in result

    # assert client secret is hashed

    assert result["client_secret"].startswith("pbkdf2_sha256")

    # test unauthenticated user
    response = account_objects.api_client_anon.get(
        reverse("account_api:org-federated-auth", args=(account_objects.org.slug,))
    )

    assert response.status_code == 403


def test_federated_auth_create(db, account_objects):
    """
    Tests creating AuthFederation for an organization.
    """

    response = account_objects.api_client.post(
        reverse(
            "account_api:org-create-federated-auth", args=(account_objects.org.slug,)
        )
    )

    assert response.status_code == 200
    result = response.json()["data"][0]
    assert "id" in result
    assert result["org"] == account_objects.org.id
    assert "client_id" in result
    assert "client_secret" in result

    # assert client secret is not hashed
    assert not result["client_secret"].startswith("pbkdf2_sha256")

    # test that second call errors with 400 Bad request
    # "An OAuth application already exists for this organization"

    response = account_objects.api_client.post(
        reverse(
            "account_api:org-create-federated-auth", args=(account_objects.org.slug,)
        )
    )

    assert response.status_code == 400
    print(response.json())
    assert response.json()["errors"]["non_field_errors"] == [
        "An OAuth application already exists for this organization."
    ]

    # test unauthenticated user
    response = account_objects.api_client_anon.post(
        reverse(
            "account_api:org-create-federated-auth", args=(account_objects.org.slug,)
        )
    )

    assert response.status_code == 403


def test_federated_auth_regenerate(db, account_objects):
    """
    Tests regenerating AuthFederation for an organization.
    """

    auth_info = federation_models.AuthFederation.create_for_org(
        account_objects.org, user=account_objects.user
    )

    response = account_objects.api_client.post(
        reverse(
            "account_api:org-regenerate-federated-auth",
            args=(account_objects.org.slug,),
        )
    )

    assert response.status_code == 200
    result = response.json()["data"][0]
    assert "id" in result
    assert result["org"] == account_objects.org.id
    assert "client_id" in result
    assert "client_secret" in result

    # assert client secret is not hashed
    assert not result["client_secret"].startswith("pbkdf2_sha256")

    # assert client secret is different from previous
    assert result["client_secret"] != auth_info.client_secret

    # test unauthenticated user
    response = account_objects.api_client_anon.post(
        reverse(
            "account_api:org-regenerate-federated-auth",
            args=(account_objects.org.slug,),
        )
    )

    assert response.status_code == 403


def test_service_bridge_federated_service_urls_list(db, account_objects):
    """
    Tests listing federated service URLs for an organization
    """

    auth_info = federation_models.AuthFederation.create_for_org(
        account_objects.org, user=account_objects.user
    )

    service_id = account_objects.federated_service_support.id

    # Create a test federated service URL for the organization
    service_url = federation_models.FederatedServiceURL.objects.create(
        url="https://example.com/federated-service",
        service_id=service_id,
        auth=auth_info.auth,
    )

    # create lookup tag
    federation_models.FederatedServiceURLTag.objects.create(
        service_url=service_url, tag="test-tag"
    )

    # send api request to reverse of service-bridge-data-federated_service_url-list
    api_url = reverse(
        "service_bridge_api:service-bridge-data-federated_service_url-list",
    )
    response = account_objects.api_client.get(f"{api_url}?org={account_objects.org.slug}&tags=test-tag")

    assert response.status_code == 200
    data = response.json()

    assert len(data["data"]) == 1
    assert data["data"][0]["url"] == "https://example.com/federated-service"
    assert data["data"][0]["service"] == service_id
    assert data["data"][0]["org"] == account_objects.org.slug
    assert data["data"][0]["tags"] == ["test-tag"]

    # now test a non existent tag

    response = account_objects.api_client.get(f"{api_url}?org={account_objects.org.slug}&tags=non-existent-tag")
    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 0