import django_devicectl.models as models
from django.urls import reverse


def test_get_vlan(db, account_objects):
    client = account_objects.api_client
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

    api_url = reverse("service_bridge_api:service-bridge-data-vlan-list")
    response = client.get(f"{api_url}?id={vlan.id}")

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["name"] == vlan.name
    assert data["data"][0]["slug"] == vlan.slug
    assert data["data"][0]["description"] == vlan.description
    assert data["data"][0]["facility_name"] == facility.name
    assert data["data"][0]["facility_slug"] == facility.slug


def test_get_vlan_by_org(db, account_objects):
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

    api_url = reverse("service_bridge_api:service-bridge-data-vlan-list")
    response = client.get(f"{api_url}?org_slug={org.slug}")

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["name"] == vlan.name
    assert data["data"][0]["slug"] == vlan.slug
    assert data["data"][0]["description"] == vlan.description
    assert data["data"][0]["facility_name"] == facility.name
    assert data["data"][0]["facility_slug"] == facility.slug


def test_get_physical_port_stats(db, account_objects):
    client = account_objects.api_client
    physical_port = account_objects.physical_ports[0]
    device = account_objects.device
    logical_port = account_objects.logical_port
    bgp_stats = [
        {
            "up": True,
            "asn": "21804",
            "name": "AS21804_1",
            "state": "Established",
            "address": "208.115.137.45",
            "protocol": "BGP",
            "router_id": "216.218.253.39",
            "last_change": "2010-06-29 00:00",
            "routes_exported": 57,
            "routes_imported": 10875,
            "routeserver_router_id": "208.115.137.251",
            "import_updates_ignored": 109628,
            "export_updates_accepted": 23207,
            "export_updates_filtered": 0,
            "export_updates_received": 4382694,
            "export_updates_rejected": 4359424,
            "import_updates_accepted": 117343,
            "import_updates_filtered": 11147,
            "import_updates_received": 238118,
            "import_updates_rejected": 0,
            "import_withdraws_ignored": 17682,
            "export_withdraws_accepted": 113,
            "export_withdraws_received": 97579,
            "import_withdraws_accepted": 97529,
            "import_withdraws_received": 105850,
            "import_withdraws_rejected": 0,
            "routeserver_hostname": "rs1.phx010.ix.dlrglobal.net",
        },
        {
            "up": True,
            "asn": "21804",
            "name": "AS21804_2",
            "state": "Established",
            "address": "2001:504:0:4:0:2:1804:1",
            "protocol": "BGP",
            "router_id": "216.218.253.39",
            "last_change": "2010-06-29 00:00",
            "routes_exported": 45,
            "routes_imported": 50199,
            "routeserver_router_id": "208.115.137.251",
            "import_updates_ignored": 501861,
            "export_updates_accepted": 4012,
            "export_updates_filtered": 0,
            "export_updates_received": 9950629,
            "export_updates_rejected": 9800708,
            "import_updates_accepted": 5580213,
            "import_updates_filtered": 901396,
            "import_updates_received": 6983470,
            "import_updates_rejected": 0,
            "import_withdraws_ignored": 919054,
            "export_withdraws_accepted": 97,
            "export_withdraws_received": 3471224,
            "import_withdraws_accepted": 3617089,
            "import_withdraws_received": 3734492,
            "import_withdraws_rejected": 0,
            "routeserver_hostname": "rs1.phx010.ix.dlrglobal.net",
        },
    ]
    device_metrics = {
        "id": 1,
        "name": "Ethernet1",
        "size": 0,
        "device": device.id,
        "grainy": f"physical_port.1.1",
        "metric": {
            "ceos00.interfaces_counters.0.Ethernet1.rx_errors": 0,
            "ceos00.interfaces_counters.0.Ethernet1.rx_octets": 27714716,
            "ceos00.interfaces_counters.0.Ethernet1.tx_errors": 0,
            "ceos00.interfaces_counters.0.Ethernet1.tx_octets": 8732,
            "ceos00.interfaces_counters.0.Ethernet1.rx_discards": 0,
            "ceos00.interfaces_counters.0.Ethernet1.tx_discards": 0,
            "ceos00.interfaces_counters.0.Ethernet1.rx_unicast_packets": 0,
            "ceos00.interfaces_counters.0.Ethernet1.tx_unicast_packets": 0,
            "ceos00.interfaces_counters.0.Ethernet1.rx_broadcast_packets": 0,
            "ceos00.interfaces_counters.0.Ethernet1.rx_multicast_packets": 216268,
            "ceos00.interfaces_counters.0.Ethernet1.tx_broadcast_packets": 0,
            "ceos00.interfaces_counters.0.Ethernet1.tx_multicast_packets": 118,
            "ceos00.optics.0.Ethernet1.physical_channels.channel.0.index": 0,
            "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.input_power.avg": -2.9,
            "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.input_power.max": -2.8,
            "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.input_power.min": -3.1,
            "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.output_power.avg": 1.7,
            "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.output_power.max": 1.9,
            "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.output_power.min": 1.6,
            "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.input_power.instant": -3.0,
            "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.output_power.instant": 1.8,
            "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.laser_bias_current.avg": 9.7,
            "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.laser_bias_current.max": 9.9,
            "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.laser_bias_current.min": 9.6,
            "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.laser_bias_current.instant": 9.8,
        },
        "status": "ok",
        "description": "Sample physical port test",
        "device_name": "Test Device",
        "display_name": "Ethernet1",
        "logical_port": logical_port.id,
        "logical_port_name": "Test Logical Port",
    }

    physical_port_stats = models.PhysicalPortStats(
        physical_port=physical_port,
        data={
            "device_metrics": device_metrics,
            "bgp_stats": bgp_stats,
        },
    )
    physical_port_stats.save()

    api_url = reverse("service_bridge_api:service-bridge-data-physical_port_stats-list")
    response = client.get(f"{api_url}?physical_port={physical_port.id}")

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["data"]["bgp_stats"] == bgp_stats
    assert data["data"][0]["data"]["device_metrics"] == device_metrics
