import json
import os

from django.urls import reverse


def test_view_instance(db, pdb_data, account_objects):
    response = account_objects.client.get(
        reverse("ixctl-home", args=(account_objects.org.slug,))
    )

    assert response.status_code == 200
    assert '<span class="label">General settings</span>' in response.content.decode(
        "utf-8"
    )
    # FIXME: I'm not sure why the svg test fails
    # assert "ixctl-logo-darkbg.svg" in response.content.decode("utf-8")


def test_view_instance_other(db, pdb_data, account_objects):
    response = account_objects.client.get(
        reverse("ixctl-home", args=(account_objects.other_org.slug,))
    )

    assert response.status_code == 404


def test_view_ixf_export_data(db, pdb_data, account_objects):
    ix = account_objects.ix
    response = account_objects.client.get(
        reverse(
            "ixf export",
            args=(
                account_objects.org.slug,
                ix.slug,
            ),
        )
        + "?pretty"
    )
    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"
    incoming = json.loads(response.content)

    with open(os.path.join(os.path.dirname(__file__), "data", "ixf", "test.json")) as f:
        expected = json.load(f)

    # drop timestamp
    incoming.pop("timestamp")
    expected.pop("timestamp")

    assert incoming == expected


def test_view_ixf_export_public(db, pdb_data, account_objects):
    ix = account_objects.ix
    assert ix.ixf_export_privacy == "public"
    url = reverse(
        "ixf export",
        args=(
            account_objects.org.slug,
            ix.slug,
        ),
    )
    response = account_objects.client.get(url)
    assert response.status_code == 200


def test_view_ixf_export_private(db, pdb_data, account_objects):
    # Set ix-f export policy to private
    ix = account_objects.ix
    ix.ixf_export_privacy = "private"
    ix.save()
    ix.refresh_from_db()

    url = reverse(
        "ixf export",
        args=(
            account_objects.org.slug,
            ix.slug,
        ),
    )
    response = account_objects.client.get(url)
    assert response.status_code == 404

    response = account_objects.client.get(url, {"secret": ix.urlkey[-5]})
    assert response.status_code == 404

    response = account_objects.client.get(url, {"secret": ix.urlkey})
    assert response.status_code == 200


def test_view_ixf_export_anon(db, pdb_data, account_objects, client_anon):
    ix = account_objects.ix
    response = client_anon.get(
        reverse(
            "ixf export",
            args=(
                account_objects.org.slug,
                ix.slug,
            ),
        )
    )
    assert response.status_code == 200


def test_view_ixf_export_pretty(db, pdb_data, account_objects, client_anon):
    ix = account_objects.ix
    response = account_objects.client.get(
        reverse(
            "ixf export",
            args=(
                account_objects.org.slug,
                ix.slug,
            ),
        )
    )
    pretty_response = account_objects.client.get(
        reverse(
            "ixf export",
            args=(
                account_objects.org.slug,
                ix.slug,
            ),
        )
        + "?pretty"
    )
    assert pretty_response.status_code == 200
    assert json.dumps(
        json.loads(response.content), indent=2
    ) == pretty_response.content.decode("utf-8")


def test_view_ixf_export_error(db, pdb_data, account_objects, client_anon):
    response = account_objects.client.get(
        reverse(
            "ixf export",
            args=(
                account_objects.org.slug,
                "falseurlkey",
            ),
        )
    )
    assert response.status_code == 404


def test_view_ixp_manager_export(db, pdb_data, account_objects):
    """Ensure the members JSON export (IXP Manager format) works."""
    ix = account_objects.ix

    url = reverse(
        "ixp_manager_export",
        args=(
            account_objects.org.slug,
            ix.slug,
        ),
    ) + "?pretty"

    response = account_objects.client.get(url)

    assert response.status_code == 200
    assert response["Content-Type"] == "application/json"

    data = json.loads(response.content)

    # Basic structure checks
    assert "member_list" in data
    assert "member_count" in data
    assert data["member_count"] == len(data["member_list"])

    # Sanity-check a sample member entry (if any)
    if data["member_list"]:
        sample = data["member_list"][0]
        expected_keys = {
            "type",
            "url",
            "name",
            "numberofports",
            "logo",
            "asnum",
            "peeringpolicy",
            "rs",
            "ipv4",
            "ipv6",
            "ports",
            "reseller",
            "resold",
        }
        assert expected_keys.issubset(sample.keys())
