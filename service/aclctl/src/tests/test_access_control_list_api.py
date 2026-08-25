import json

from django.urls import reverse

from tests.helpers import assert_expected, strip_api_fields


def test_access_control_list_get(db, account_objects, data_AccessControlList_api_get):
    org = account_objects.org

    client = account_objects.api_client

    # Check if acl-test(created in fixtures.py) exists using get
    response = client.get(
        reverse(
            "aclctl_api:access_control_list-detail",
            args=(org.slug, account_objects.test_acl.slug),
        )
    )

    assert response.status_code == 200
    assert_expected(response, strip_api_fields(data_AccessControlList_api_get.expected))


def test_access_control_list_create(
    db, account_objects, data_AccessControlList_api_create
):
    org = account_objects.org

    client = account_objects.api_client

    # create Access Control List called acl-1
    response = client.post(
        reverse("aclctl_api:access_control_list-list", args=(org.slug,)),
        data=json.loads(data_AccessControlList_api_create.input),
        format="json",
    )

    # Check if acl-1 exists
    pk = json.loads(data_AccessControlList_api_create.input)["slug"]
    response = client.get(
        reverse("aclctl_api:access_control_list-detail", args=(org.slug, pk))
    )

    assert response.status_code == 200
    assert_expected(
        response, strip_api_fields(data_AccessControlList_api_create.expected)
    )


def test_access_control_list_list(db, account_objects, data_AccessControlList_api_list):
    org = account_objects.org

    client = account_objects.api_client

    # create Access Control Lists
    response = client.post(
        reverse("aclctl_api:access_control_list-list", args=(org.slug,)),
        data=json.loads(data_AccessControlList_api_list.input),
        format="json",
    )

    response.status_code == 200

    # test list for acl-test and created acl
    response = client.get(
        reverse("aclctl_api:access_control_list-list", args=(org.slug,))
    )

    assert response.status_code == 200
    assert_expected(
        response, strip_api_fields(data_AccessControlList_api_list.expected)
    )


def test_access_control_list_update(
    db, account_objects, data_AccessControlList_api_update
):
    org = account_objects.org

    client = account_objects.api_client

    # update acl-test
    response = client.put(
        reverse(
            "aclctl_api:access_control_list-detail",
            args=(org.slug, account_objects.test_acl.slug),
        ),
        data=json.loads(data_AccessControlList_api_update.input),
        format="json",
    )

    # check if acl got updated
    response = client.get(
        reverse("aclctl_api:access_control_list-list", args=(org.slug,))
    )

    assert response.status_code == 200
    assert_expected(
        response, strip_api_fields(data_AccessControlList_api_update.expected)
    )


def test_access_control_list_delete(
    db, account_objects, data_AccessControlList_api_delete
):
    org = account_objects.org

    client = account_objects.api_client

    response = client.post(
        reverse("aclctl_api:access_control_list-list", args=(org.slug,)),
        data=json.loads(data_AccessControlList_api_delete.input)["acl-keep"],
        format="json",
    )

    response.status_code == 200

    # delete acl-test
    response = client.delete(
        reverse(
            "aclctl_api:access_control_list-detail",
            args=(org.slug, account_objects.test_acl.slug),
        )
    )

    assert response.status_code == 200
    acl = response.json()["data"][0]
    assert acl["id"] == account_objects.test_acl.id
    assert acl["num_filters"] == 1

    # check list to see if acl deleted
    response = client.get(
        reverse("aclctl_api:access_control_list-list", args=(org.slug,))
    )

    assert response.status_code == 200
    assert_expected(
        response, strip_api_fields(data_AccessControlList_api_delete.expected)
    )
