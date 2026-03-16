import json
from unittest.mock import patch

import django_ixctl.models as models
import pytest
from django.urls import reverse


def test_ix_import_peeringdb(db, pdb_data, account_objects):
    org = account_objects.org

    client = account_objects.api_client

    response = client.post(
        reverse("ixctl_api:ix-import-peeringdb", args=(org.slug,)),
        {"pdb_ix_id": 239},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["data"][0]["pdb_id"] == 239


def test_ix_import_peeringdb_invalid(db, pdb_data, account_objects):
    org = account_objects.org
    client = account_objects.api_client
    response = client.post(
        reverse("ixctl_api:ix-import-peeringdb", args=(org.slug,)),
        {"pdb_ix_id": 10000000000000},
    )
    assert response.status_code == 400
    data = response.json()
    assert "Unknown peeringdb exchange" in data["errors"]["pdb_ix_id"]


def test_ix_import_peeringdb_reimport(db, pdb_data, account_objects):
    org = account_objects.org
    client = account_objects.api_client
    client.post(
        reverse("ixctl_api:ix-import-peeringdb", args=(org.slug,)), {"pdb_ix_id": 239}
    )
    response = client.post(
        reverse("ixctl_api:ix-import-peeringdb", args=(org.slug,)), {"pdb_ix_id": 239}
    )
    assert response.status_code == 400
    data = response.json()
    assert "You have already imported this exchange" in data["errors"]["pdb_ix_id"]


def test_ix_list(db, pdb_data, account_objects):
    ix = account_objects.ix
    client = account_objects.api_client
    org = account_objects.org

    response = client.get(reverse("ixctl_api:ix-list", args=(org.slug,)))

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["pdb_id"] == ix.pdb_id
    assert data[0]["urlkey"] == ix.urlkey
    assert data[0]["name"] == ix.pdb.name
    assert data[0]["id"] == ix.id
    assert data[0]["status"] == ix.status


def test_ix_retrieve(db, pdb_data, account_objects):
    ix = account_objects.ix
    client = account_objects.api_client
    org = account_objects.org

    response = client.get(reverse("ixctl_api:ix-detail", args=(org.slug, ix.slug)))

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["pdb_id"] == ix.pdb_id
    assert data[0]["urlkey"] == ix.urlkey
    assert data[0]["name"] == ix.pdb.name
    assert data[0]["id"] == ix.id
    assert data[0]["status"] == ix.status


def test_ix_create(db, pdb_data, account_objects):
    client = account_objects.api_client
    org = account_objects.org

    data = {"name": "test IX new"}
    response = client.post(
        reverse("ixctl_api:ix-list", args=(org.slug,)),
        json.dumps(data),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["pdb_id"] is None
    assert data[0]["name"] == "test IX new"
    assert models.InternetExchange.objects.filter(name="test IX new").exists()


def test_ix_put_ixf_export_policy(db, pdb_data, account_objects):
    ix = account_objects.ix
    client = account_objects.api_client
    org = account_objects.org

    assert ix.ixf_export_privacy == "public"

    data = {
        "name": ix.name,
        "pdb_id": ix.pdb_id,
        "urlkey": "new url key",
        "slug": ix.slug,
        "ixf_export_privacy": "private",
        "instance": ix.instance.id,
    }

    response = client.put(
        reverse(
            "ixctl_api:ix-detail",
            args=(
                org.slug,
                ix.slug,
            ),
        ),
        json.dumps(data),
        content_type="application/json",
    )

    print(response.json())

    assert response.status_code == 200
    output = response.json()["data"]
    assert len(output) == 1

    ix.refresh_from_db()
    assert ix.ixf_export_privacy == data["ixf_export_privacy"]
    assert ix.urlkey == data["urlkey"]


def test_ix_put_slug(db, pdb_data, account_objects):
    ix = account_objects.ix
    client = account_objects.api_client
    org = account_objects.org

    data = {
        "name": ix.name,
        "pdb_id": ix.pdb_id,
        "urlkey": ix.urlkey,
        "slug": "changed-slug",
    }
    response = client.put(
        reverse(
            "ixctl_api:ix-detail",
            args=(
                org.slug,
                ix.slug,
            ),
        ),
        json.dumps(data),
        content_type="application/json",
    )

    assert response.status_code == 200
    output = response.json()["data"]
    assert len(output) == 1

    ix.refresh_from_db()
    assert ix.slug == data["slug"]

    assert output[0]["slug"] == data["slug"]
    assert output[0]["name"] == data["name"]
    assert output[0]["pdb_id"] == data["pdb_id"]


def test_ix_put_slug_invalid(db, pdb_data, account_objects):
    ix = account_objects.ix
    client = account_objects.api_client
    org = account_objects.org

    data = {
        "name": ix.name,
        "pdb_id": ix.pdb_id,
        "urlkey": ix.urlkey,
        "slug": "invalid slug",
    }
    response = client.put(
        reverse(
            "ixctl_api:ix-detail",
            args=(
                org.slug,
                ix.slug,
            ),
        ),
        json.dumps(data),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert "slug" in list(response.json()["errors"].keys())


def test_ix_create_invalid(db, pdb_data, account_objects):
    client = account_objects.api_client
    org = account_objects.org

    data = {"name": None}
    response = client.post(
        reverse("ixctl_api:ix-list", args=(org.slug,)),
        json.dumps(data),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["errors"] == {"name": ["This field may not be null."]}


def test_ix_members(db, pdb_data, account_objects):
    ix = account_objects.ix
    client = account_objects.api_client
    org = account_objects.org

    ixmember = ix.member_set.first()

    response = client.get(reverse("ixctl_api:member-list", args=(org.slug, ix.slug)))

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 2
    assert data[0]["pdb_id"] == ixmember.pdb_id
    assert data[0]["id"] == ixmember.id
    assert data[0]["status"] == ixmember.status
    assert data[0]["ixf_member_type"] == ixmember.ixf_member_type
    assert data[0]["ixf_state"] == ixmember.ixf_state
    assert data[0]["display_name"] == ixmember.display_name
    assert data[0]["ipaddr4"] == f"{ixmember.ipaddr4}"
    assert data[0]["ipaddr6"] == f"{ixmember.ipaddr6}"
    assert data[0]["is_rs_peer"] == ixmember.is_rs_peer
    assert data[0]["speed"] == ixmember.speed


def test_ix_delete_member(db, pdb_data, account_objects):
    ix = account_objects.ix
    client = account_objects.api_client
    org = account_objects.org

    ixmember = ix.member_set.first()

    response = client.delete(
        reverse("ixctl_api:member-detail", args=(org.slug, ix.slug, ixmember.id)),
        content_type="application/json",
    )
    assert response.status_code == 200

    assert (
        models.InternetExchangeMember.objects.filter(id=ixmember.id).exists() is False
    )


def test_ix_create_member(db, pdb_data, account_objects):
    ix = account_objects.ix
    client = account_objects.api_client
    org = account_objects.org

    response = client.post(
        reverse("ixctl_api:member-list", args=(org.slug, ix.slug)),
        json.dumps(
            {
                "asn": 63311,
                "ixf_state": "active",
                "ixf_member_type": "peering",
                "name": "",
                "ippadr4": "206.41.111.20",
                "ipaddr6": "2001:504:41:111::20",
                "port_size": 1,
                "port_quantity": 1,
                "lag": False,
                "is_rs_peer": False,
            }
        ),
        content_type="application/json",
    )

    data = response.json()["data"]

    print(response.json())

    assert response.status_code == 200

    assert models.InternetExchangeMember.objects.filter(id=data[0]["id"]).exists()


def test_ix_create_member_invalid(db, pdb_data, account_objects):
    ix = account_objects.ix
    client = account_objects.api_client
    org = account_objects.org

    ixmember = ix.member_set.first()

    response = client.post(
        reverse("ixctl_api:member-list", args=(org.slug, ix.slug)),
        json.dumps(
            {
                "asn": 63311,
                "ixf_state": "active",
                "ixf_member_type": "peering",
                "name": "",
                "ippadr4": None,
                "ipaddr6": f"{ixmember.ipaddr6}",
                "port_size": 1,
                "port_quantity": 1,
                "lag": False,
                "is_rs_peer": False,
            }
        ),
        content_type="application/json",
    )
    errors = response.json()["errors"]
    assert response.status_code == 400
    assert errors == {
        "non_field_errors": ["IPv6 address exists already in this exchange"]
    }


def test_ix_edit_member(db, pdb_data, account_objects):
    ix = account_objects.ix
    client = account_objects.api_client
    org = account_objects.org

    ixmember = ix.member_set.first()

    response = client.put(
        reverse("ixctl_api:member-detail", args=(org.slug, ix.slug, ixmember.id)),
        json.dumps(
            {
                "id": ixmember.id,
                "ix": ixmember.ix.id,
                "asn": 63311,
                "ixf_state": "active",
                "ixf_member_type": "peering",
                "name": "override",
                "ipaddr4": "206.41.111.20",
                "ipaddr6": "2001:504:41:111::20",
                "port_size": ixmember.port_size,
                "port_quantity": ixmember.port_quantity,
                "lag": ixmember.lag,
                "is_rs_peer": False,
            }
        ),
        content_type="application/json",
    )
    assert response.status_code == 200

    ixmember.refresh_from_db()
    assert ixmember.name == "override"
    assert f"{ixmember.ipaddr4}" == "206.41.111.20"
    assert f"{ixmember.ipaddr6}" == "2001:504:41:111::20"


def test_ix_edit_member_invalid(db, pdb_data, account_objects):
    ix = account_objects.ix
    client = account_objects.api_client
    org = account_objects.org

    ixmember = ix.member_set.first()

    response = client.put(
        reverse("ixctl_api:member-detail", args=(org.slug, ix.slug, ixmember.id)),
        json.dumps(
            {
                "id": ixmember.id,
                "ix": ixmember.ix.id,
                "asn": 63311,
                "ixf_state": "active",
                "ixf_member_type": "peering",
                "name": "override",
                "ipaddr4": "",
                "ipaddr6": "",
                "port_size": ixmember.port_size,
                "port_quantity": ixmember.port_quantity,
                "lag": ixmember.lag,
                "is_rs_peer": False,
            }
        ),
        content_type="application/json",
    )
    errors = response.json()["errors"]
    assert response.status_code == 400
    assert errors == {
        "ipaddr4": ["Input required for IPv4 or IPv6"],
        "ipaddr6": ["Input required for IPv4 or IPv6"],
    }


def test_edit_member_invalid_quantity(db, pdb_data, account_objects):
    ix = account_objects.ix
    client = account_objects.api_client
    org = account_objects.org

    ixmember = ix.member_set.first()

    response = client.put(
        reverse("ixctl_api:member-detail", args=(org.slug, ix.slug, ixmember.id)),
        json.dumps(
            {
                "id": ixmember.id,
                "ix": ixmember.ix.id,
                "asn": 63311,
                "ixf_state": "active",
                "ixf_member_type": "peering",
                "name": "override",
                "ipaddr4": "206.41.111.20",
                "ipaddr6": "2001:504:41:111::20",
                "port_size": 10,
                "port_quantity": 3,
                # lag is False but port_quantity is 3, this should be invalid
                "lag": False,
                "is_rs_peer": False,
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 400

    errors = response.json()["errors"]

    assert errors == {"port_quantity": ["Must be 1 if LAG is not set"]}


def test_list_routeservers(db, pdb_data, account_objects):
    ix = account_objects.ix
    client = account_objects.api_client
    org = account_objects.org
    assert account_objects.routeserver
    response = client.get(
        reverse("ixctl_api:routeserver-list", args=(org.slug, ix.slug))
    )
    assert response.status_code == 200
    data = response.json()["data"]

    assert len(data) == ix.rs_set.count()
    assert data[0]["name"] == ix.rs_set.first().name


def test_list_routeservers_no_liveness(db, pdb_data, account_objects):
    """When routeserver has no liveness set, config_last_fetched_time should be None."""
    ix = account_objects.ix
    client = account_objects.api_client
    org = account_objects.org
    rs = account_objects.routeserver
    assert rs.liveness is None

    with patch.object(models.Routeserver, "preload_events"):
        response = client.get(
            reverse("ixctl_api:routeserver-list", args=(org.slug, ix.slug))
        )

    assert response.status_code == 200
    data = response.json()["data"]
    for rs_data in data:
        assert rs_data["config_last_fetched_time"] is None


def test_list_routeservers_with_liveness(db, pdb_data, account_objects):
    """When routeserver has liveness set, config_last_fetched_time should reflect it."""
    from django.utils import timezone

    ix = account_objects.ix
    client = account_objects.api_client
    org = account_objects.org
    rs = account_objects.routeserver

    now = timezone.now()
    rs.liveness = now
    rs.save()

    with patch.object(models.Routeserver, "preload_events"):
        response = client.get(
            reverse("ixctl_api:routeserver-list", args=(org.slug, ix.slug))
        )

    assert response.status_code == 200
    data = response.json()["data"]
    for rs_data in data:
        if rs_data["id"] == rs.id:
            assert rs_data["config_last_fetched_time"] == now.strftime(
                "%Y-%m-%d %H:%M:%S"
            )


def test_create_routeserver(db, pdb_data, account_objects):
    ix = account_objects.ix
    client = account_objects.api_client
    org = account_objects.org
    assert account_objects.routeserver
    payload = {
        "asn": 63311,
        "graceful_shutdown": False,
        "ix": 1,
        "max_as_path_length": 32,
        "name": "New rs",
        "no_export_action": "pass",
        "router_id": "194.168.0.1",
    }
    response = client.post(
        reverse("ixctl_api:routeserver-list", args=(org.slug, ix.slug)),
        json.dumps(payload),
        content_type="application/json",
    )

    # Response is correct
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "New rs"
    assert data[0]["router_id"] == "194.168.0.1"

    # Changes are persisted to db
    assert models.Routeserver.objects.filter(id=data[0]["id"]).exists()
    new_rs = models.Routeserver.objects.filter(id=data[0]["id"]).first()
    assert new_rs.name == "New rs"
    ix.refresh_from_db()
    assert ix.rs_set.count() == 2


def test_create_routeserver_dupe_router_id_in_org(db, pdb_data, account_objects):
    ix = account_objects.ix
    client = account_objects.api_client
    org = account_objects.org
    assert account_objects.routeserver
    payload = {
        "asn": 63311,
        "graceful_shutdown": False,
        "ix": 1,
        "max_as_path_length": 32,
        "name": "New rs",
        "no_export_action": "pass",
        "router_id": "194.168.0.1",
    }
    response = client.post(
        reverse("ixctl_api:routeserver-list", args=(org.slug, ix.slug)),
        json.dumps(payload),
        content_type="application/json",
    )

    # Response is correct
    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "New rs"
    assert data[0]["router_id"] == "194.168.0.1"

    # Now create a new routeserver with the same router_id at
    # a different ix (but same org)
    #
    # should result in a validation error

    ix2 = models.InternetExchange.objects.create(
        instance=ix.instance,
        name="ix2",
        pdb_id=2,
        urlkey="ix2",
        status="ok",
        slug="ix2",
    )

    payload = {
        "asn": 63311,
        "graceful_shutdown": False,
        "ix": ix2.id,
        "max_as_path_length": 32,
        "name": "New rs2",
        "no_export_action": "pass",
        "router_id": "194.168.0.1",
    }

    response = client.post(
        reverse("ixctl_api:routeserver-list", args=(org.slug, ix2.slug)),
        json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert response.json()["errors"]["router_id"] == [
        "Router ID already exists for this organization"
    ]


def test_delete_routeserver(db, pdb_data, account_objects):
    ix = account_objects.ix
    rs = account_objects.routeserver
    client = account_objects.api_client
    org = account_objects.org
    response = client.delete(
        reverse("ixctl_api:routeserver-detail", args=(org.slug, ix.slug, rs.id)),
        content_type="application/json",
    )

    assert response.status_code == 200
    # Response is correct
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "test routeserver"
    assert data[0]["router_id"] == "192.168.0.1"

    # Changes are persisted to db
    assert not models.Routeserver.objects.filter(id=rs.id).exists()


def test_update_routeserver(db, pdb_data, account_objects):
    ix = account_objects.ix
    rs = account_objects.routeserver
    client = account_objects.api_client
    org = account_objects.org
    payload = {
        "ars_type": "bird",
        "asn": 63311,
        "graceful_shutdown": False,
        "id": 1,
        "ix": models.InternetExchange.objects.first().id,
        "max_as_path_length": 32,
        "name": "changed name",  # changed
        "no_export_action": "pass",
        "router_id": "193.168.0.1",  # changed
        "rpki_bgp_origin_validation": False,
        "status": "ok",
    }
    response = client.put(
        reverse("ixctl_api:routeserver-detail", args=(org.slug, ix.slug, rs.id)),
        json.dumps(payload),
        content_type="application/json",
    )

    print(response.json())

    assert response.status_code == 200
    # Response is correct
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "changed name"
    assert data[0]["router_id"] == "193.168.0.1"

    # Changes are persisted to db
    routeserver = models.Routeserver.objects.filter(id=rs.id).first()
    assert routeserver.name == "changed name"
    assert str(routeserver.router_id) == "193.168.0.1"

    # Unchanged fields remain unchanged
    assert data[0]["ars_type"] == routeserver.ars_type


def test_update_routeserver_dupe_router_id_in_org(db, pdb_data, account_objects):
    """
    Test that updating a routeserver to have a router_id that already exists in the org
    results in a validation error
    """

    ix = account_objects.ix
    rs = account_objects.routeserver
    client = account_objects.api_client
    org = account_objects.org

    # different ix
    ix2 = models.InternetExchange.objects.create(
        instance=ix.instance,
        name="ix2",
        pdb_id=2,
        urlkey="ix2",
        status="ok",
        slug="ix2",
    )

    # Create a new routeserver with a different router_id
    rs2 = models.Routeserver.objects.create(
        ix=ix2,
        name="rs2",
        asn=63311,
        router_id="193.168.0.2",
        rpki_bgp_origin_validation=False,
        ars_type="bird",
        max_as_path_length=32,
        operational_status="operational",
    )

    # Update the first routeserver to have the same router_id as the second

    payload = {
        "ars_type": "bird",
        "asn": 63311,
        "graceful_shutdown": False,
        "id": rs.id,
        "ix": ix.id,
        "max_as_path_length": 32,
        "name": "changed name",  # changed
        "no_export_action": "pass",
        "router_id": rs2.router_id,  # changed
        "rpki_bgp_origin_validation": False,
        "status": "ok",
    }

    response = client.put(
        reverse("ixctl_api:routeserver-detail", args=(org.slug, ix.slug, rs.id)),
        json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 400
    print(response.json())
    assert response.json()["errors"]["router_id"] == [
        "Router ID already exists for this organization"
    ]


def test_retrieve_routeserverconfig(db, pdb_data, account_objects):
    rs = account_objects.routeserver
    rs.routeserver_config
    # routeserver_config.generate()
    ix = account_objects.ix
    client = account_objects.api_client
    org = account_objects.org
    print(
        reverse(
            "ixctl_api:config/routeserver-detail", args=(org.slug, ix.slug, rs.name)
        )
    )
    response = client.get(
        reverse(
            "ixctl_api:config/routeserver-detail", args=(org.slug, ix.slug, rs.name)
        )
    )
    assert response.status_code == 200

    response_plain = client.get(
        reverse("ixctl_api:config/routeserver-plain", args=(org.slug, ix.slug, rs.name))
    )
    assert response_plain.status_code == 200


def test_set_operational_status_for_routeserver(db, pdb_data, account_objects):
    ix = account_objects.ix
    rs = account_objects.routeserver
    client = account_objects.api_client
    org = account_objects.org

    routeserver = models.Routeserver.objects.filter(id=rs.id).first()
    assert routeserver.operational_status == "operational"

    payload = {"operational_status": "down"}

    response = client.post(
        reverse(
            "ixctl_api:routeserver-operational-status", args=(org.slug, ix.slug, rs.id)
        ),
        json.dumps(payload),
        content_type="application/json",
    )

    assert response.status_code == 200

    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["operational_status"] == "down"

    # Changes are persisted to db
    routeserver = models.Routeserver.objects.filter(id=rs.id).first()
    assert routeserver.operational_status == "down"


def test_send_empty_operational_status_object(db, pdb_data, account_objects):
    ix = account_objects.ix
    rs = account_objects.routeserver
    client = account_objects.api_client
    org = account_objects.org

    routeserver = models.Routeserver.objects.filter(id=rs.id).first()
    assert routeserver.operational_status == "operational"

    payload = {}  # empty payload with operational_status key

    response = client.post(
        reverse(
            "ixctl_api:routeserver-operational-status", args=(org.slug, ix.slug, rs.id)
        ),
        json.dumps(payload),
        content_type="application/json",
    )
    print(response.json())
    assert response.status_code == 400
    assert response.json()["errors"]["operational_status"] == [
        "This field is required."
    ]

    # Changes are persisted to db
    routeserver = models.Routeserver.objects.filter(id=rs.id).first()
    assert routeserver.operational_status == "operational"


def test_create_traffic_alert_config(db, pdb_data, account_objects):
    client = account_objects.api_client
    org = account_objects.org
    ix = account_objects.ix

    response = client.post(
        reverse("ixctl_api:traffic_alert_config-list", args=(org.slug, ix.slug)),
        json.dumps(
            {
                "ix": ix.id,
                "traffic_level": 90,
                "time_period": 5,
                "operator_emails": True,
                "member_emails": True,
                "operator_emails_max_frequency": 7,
                "member_emails_max_frequency": 7,
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["ix"] == ix.id
    assert models.TrafficAlertConfig.objects.get(id=data[0]["id"]).ix.id == ix.id


def test_update_traffic_alert_config(db, pdb_data, account_objects):
    client = account_objects.api_client
    org = account_objects.org
    ix = account_objects.ix

    models.TrafficAlertConfig(
        ix=ix,
        traffic_level=90,
        time_period=5,
        operator_emails=True,
        member_emails=True,
        operator_emails_max_frequency=7,
        member_emails_max_frequency=7,
    ).save()
    traffic_alert_config = models.TrafficAlertConfig.objects.filter(ix=ix).first()

    response = client.put(
        reverse(
            "ixctl_api:traffic_alert_config-detail",
            args=(org.slug, ix.slug, traffic_alert_config.id),
        ),
        json.dumps(
            {
                "ix": ix.id,
                "member_emails": False,
                "operator_emails_max_frequency": 30,
                "member_emails_max_frequency": 90,
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["ix"] == ix.id
    assert data[0]["member_emails"] is False
    assert data[0]["operator_emails_max_frequency"] == 30
    assert data[0]["member_emails_max_frequency"] == 90

    db_traffic_alert_config = models.TrafficAlertConfig.objects.get(id=data[0]["id"])
    assert db_traffic_alert_config.member_emails is False
    assert db_traffic_alert_config.operator_emails_max_frequency == 30
    assert db_traffic_alert_config.member_emails_max_frequency == 90


def test_retrieve_traffic_alert_config(db, pdb_data, account_objects):
    client = account_objects.api_client
    org = account_objects.org
    ix = account_objects.ix

    models.TrafficAlertConfig(
        ix=ix,
        traffic_level=90,
        time_period=5,
        operator_emails=True,
        member_emails=True,
        operator_emails_max_frequency=7,
        member_emails_max_frequency=7,
    ).save()
    traffic_alert_config = models.TrafficAlertConfig.objects.filter(ix=ix).first()

    response = client.get(
        reverse(
            "ixctl_api:traffic_alert_config-detail",
            args=(org.slug, ix.slug, traffic_alert_config.id),
        ),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["ix"] == ix.id

    db_traffic_alert_config = models.TrafficAlertConfig.objects.get(id=data[0]["id"])
    assert db_traffic_alert_config.member_emails == data[0]["member_emails"]
    assert (
        db_traffic_alert_config.operator_emails_max_frequency
        == data[0]["operator_emails_max_frequency"]
    )
    assert (
        db_traffic_alert_config.member_emails_max_frequency
        == data[0]["member_emails_max_frequency"]
    )


def test_get_traffic_alert_config_by_ix(db, pdb_data, account_objects):
    client = account_objects.api_client
    org = account_objects.org
    ix = account_objects.ix

    models.TrafficAlertConfig(
        ix=ix,
        traffic_level=90,
        time_period=5,
        operator_emails=True,
        member_emails=True,
        operator_emails_max_frequency=7,
        member_emails_max_frequency=7,
    ).save()

    response = client.get(
        reverse("ixctl_api:traffic_alert_config-get-by-ix", args=(org.slug, ix.slug)),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["ix"] == ix.id

    db_traffic_alert_config = models.TrafficAlertConfig.objects.get(id=data[0]["id"])
    assert db_traffic_alert_config.member_emails == data[0]["member_emails"]
    assert (
        db_traffic_alert_config.operator_emails_max_frequency
        == data[0]["operator_emails_max_frequency"]
    )
    assert (
        db_traffic_alert_config.member_emails_max_frequency
        == data[0]["member_emails_max_frequency"]
    )


def test_create_email_template(db, pdb_data, account_objects):
    client = account_objects.api_client
    org = account_objects.org
    ix = account_objects.ix

    response = client.post(
        reverse("ixctl_api:email_template-list", args=(org.slug, ix.slug)),
        json.dumps(
            {
                "ix": ix.id,
                "type": "traffic_alert_net",
                "body": "Test email body for {{ ix.name }}",
                "name": "Traffic Alert Net",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["ix"] == ix.id
    assert models.EmailTemplate.objects.get(id=data[0]["id"]).ix.id == ix.id


def test_update_email_template(db, pdb_data, account_objects):
    client = account_objects.api_client
    org = account_objects.org
    ix = account_objects.ix

    models.EmailTemplate(
        ix=ix,
        name="Traffic Alert Net",
        body="Test email body for {{ ix.name }}",
        type="traffic_alert_net",
    ).save()
    email_template = models.EmailTemplate.objects.filter(ix=ix).first()

    body = "Test email body for {{ ix.name }} {{ downtime }}"
    name = "Traffic Alert Network"

    response = client.put(
        reverse(
            "ixctl_api:email_template-detail",
            args=(org.slug, ix.slug, email_template.id),
        ),
        json.dumps(
            {"ix": ix.id, "type": "traffic_alert_net", "body": body, "name": name}
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["ix"] == ix.id
    assert data[0]["name"] == name
    assert data[0]["body"] == body

    email_template = models.EmailTemplate.objects.get(id=data[0]["id"])
    assert email_template.body == body
    assert email_template.name == name


def test_retrieve_email_template(db, pdb_data, account_objects):
    client = account_objects.api_client
    org = account_objects.org
    ix = account_objects.ix

    models.EmailTemplate(
        ix=ix,
        name="Traffic Alert Net",
        body="Test email body for {{ ix.name }}",
        type="traffic_alert_net",
    ).save()
    email_template = models.EmailTemplate.objects.filter(ix=ix).first()

    response = client.get(
        reverse(
            "ixctl_api:email_template-detail",
            args=(org.slug, ix.slug, email_template.id),
        ),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["ix"] == ix.id

    email_template = models.EmailTemplate.objects.get(id=data[0]["id"])
    assert email_template.body == data[0]["body"]
    assert email_template.name == data[0]["name"]


def test_get_email_template_by_type(db, pdb_data, account_objects):
    client = account_objects.api_client
    org = account_objects.org
    ix = account_objects.ix
    template_type = "traffic_alert_net"

    models.EmailTemplate(
        ix=ix,
        name="Traffic Alert Net",
        body="Test email body for {{ ix.name }}",
        type=template_type,
    ).save()

    response = client.get(
        reverse(
            "ixctl_api:email_template-get-default-by-type",
            args=(org.slug, ix.slug, template_type),
        ),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["ix"] == ix.id
    assert data[0]["type"] == template_type

    email_template = models.EmailTemplate.objects.get(id=data[0]["id"])
    assert email_template.type == template_type


# TODO: Find why destry view returns 404 even after successful delete
@pytest.mark.skip
def test_delete_email_template(db, pdb_data, account_objects):
    client = account_objects.api_client
    org = account_objects.org
    ix = account_objects.ix

    models.EmailTemplate(
        ix=ix,
        name="Traffic Alert Net",
        body="Test email body for {{ ix.name }}",
        type="traffic_alert_net",
    ).save()
    email_template = models.EmailTemplate.objects.filter(ix=ix).first()

    response = client.delete(
        reverse(
            "ixctl_api:email_template-detail",
            args=(org.slug, ix.slug, email_template.id),
        ),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["ix"] == ix.id

    with pytest.raises(models.EmailTemplate.DoesNotExist):
        models.EmailTemplate.objects.get(id=data[0]["id"])


def test_preview_email_template(db, pdb_data, account_objects):
    client = account_objects.api_client
    org = account_objects.org
    ix = account_objects.ix

    traffic_alert_config = models.TrafficAlertConfig(
        ix=ix,
        traffic_level=90,
        time_period=5,
        operator_emails=True,
        member_emails=True,
        operator_emails_max_frequency=7,
        member_emails_max_frequency=7,
    )
    traffic_alert_config.save()

    models.EmailTemplate(
        ix=ix,
        name="Traffic Alert Net",
        body="Test email body for {{ ix.name }}",
        type="traffic_alert_net",
    ).save()
    email_template = models.EmailTemplate.objects.filter(ix=ix).first()

    response = client.post(
        reverse(
            "ixctl_api:email_template-preview",
            args=(org.slug, ix.slug, email_template.id),
        ),
        json.dumps(
            {
                "ix": ix.id,
                "type": "traffic_alert_net",
                "body": "Test email body for {{ ix.name }} {{ traffic_alert_config.traffic_level }}",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert (
        data[0]["body"]
        == f"Test email body for {ix.name} {traffic_alert_config.traffic_level}"
    )
