import json

from django.urls import reverse

from tests.helpers import assert_expected, strip_api_fields


def test_filter_rule_get(db, account_objects, data_FilterRule_api_get):
    org = account_objects.org

    client = account_objects.api_client

    # Check if filter rule created in fixtures.py exists using get
    response = client.get(
        reverse(
            "aclctl_api:filter_rule-detail",
            args=(org.slug, account_objects.test_filter_rule.id),
        )
    )
    assert response.status_code == 200
    assert_expected(response, strip_api_fields(data_FilterRule_api_get.expected))


def test_filter_rule_create(db, account_objects, data_FilterRule_api_create):
    org = account_objects.org

    client = account_objects.api_client

    # create new filter rule
    request = json.loads(data_FilterRule_api_create.input)
    request["access_control_list"] = account_objects.test_acl.id
    response = client.post(
        reverse("aclctl_api:filter_rule-list", args=(org.slug,)),
        data=request,
        format="json",
    )
    assert response.status_code == 200
    created_filter_rule_id = response.data["id"]

    # check if filter rule exists
    response = client.get(
        reverse(
            "aclctl_api:filter_rule-detail", args=(org.slug, created_filter_rule_id)
        )
    )
    assert response.status_code == 200
    assert_expected(response, strip_api_fields(data_FilterRule_api_create.expected))


def test_filter_rule_list(db, account_objects, data_FilterRule_api_list):
    org = account_objects.org

    client = account_objects.api_client

    # create new filter rule
    request = json.loads(data_FilterRule_api_list.input)
    request["access_control_list"] = account_objects.test_acl.id
    response = client.post(
        reverse("aclctl_api:filter_rule-list", args=(org.slug,)),
        data=request,
        format="json",
    )
    assert response.status_code == 200

    # check if filter rule list
    response = client.get(reverse("aclctl_api:filter_rule-list", args=(org.slug,)))

    assert response.status_code == 200
    assert_expected(response, strip_api_fields(data_FilterRule_api_list.expected))


def test_filter_rule_update(db, account_objects, data_FilterRule_api_update):
    org = account_objects.org

    client = account_objects.api_client

    # edit test filter rule
    request = json.loads(data_FilterRule_api_update.input)
    request["access_control_list"] = account_objects.test_acl.id
    response = client.put(
        reverse(
            "aclctl_api:filter_rule-detail",
            args=(org.slug, account_objects.test_filter_rule.id),
        ),
        data=request,
        format="json",
    )
    assert response.status_code == 200

    # check if filter rule exists
    response = client.get(reverse("aclctl_api:filter_rule-list", args=(org.slug,)))
    assert response.status_code == 200
    assert_expected(response, strip_api_fields(data_FilterRule_api_update.expected))


def test_filter_rule_delete(db, account_objects, data_FilterRule_api_delete):
    org = account_objects.org

    client = account_objects.api_client

    # create new filter rule
    request = json.loads(data_FilterRule_api_delete.input)
    request["access_control_list"] = account_objects.test_acl.id
    response = client.post(
        reverse("aclctl_api:filter_rule-list", args=(org.slug,)),
        data=request,
        format="json",
    )

    assert response.status_code == 200

    # delete test filter rule
    response = client.delete(
        reverse(
            "aclctl_api:filter_rule-detail",
            args=(org.slug, account_objects.test_filter_rule.id),
        )
    )

    assert response.status_code == 200

    # check if filter rule is deleted from list
    response = client.get(reverse("aclctl_api:filter_rule-list", args=(org.slug,)))
    assert response.status_code == 200
    assert_expected(response, strip_api_fields(data_FilterRule_api_delete.expected))
