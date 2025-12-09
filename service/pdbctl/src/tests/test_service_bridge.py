from django.urls import reverse


def test_net_list(db, pdb_data, account_objects):
    net = pdb_data.get("net")

    client = account_objects.api_client
    response = client.get(
        reverse("service_bridge_api:service-bridge-data-net-list") + "?asn=63311"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["asn"] == net.asn
    assert data[0]["name"] == net.name
    assert data[0]["id"] == net.id


def test_ix_list(db, pdb_data, account_objects):
    ix = pdb_data.get("ix")

    client = account_objects.api_client
    response = client.get(
        reverse("service_bridge_api:service-bridge-data-ix-list") + "?q=Exchange"
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == ix.name
    assert data[0]["id"] == ix.id
