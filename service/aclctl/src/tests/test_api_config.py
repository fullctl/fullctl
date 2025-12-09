from django.urls import reverse


def test_config_render(db, account_objects, data_FilterRule_api_get):
    org = account_objects.org

    client = account_objects.api_client

    # get request using acl created in fixtures.py and defaults (cisco-nexus and default)
    response = client.get(
        reverse(
            "aclctl_api:config-filter-rule",
            args=(org.slug, account_objects.test_acl.slug, "cisco-nexus", "default"),
        )
    )

    assert (
        "10 permit 123.123.123.111/32 eq 3 123.123.123.112/32 eq 5"
        in response.data["body"]
    )
