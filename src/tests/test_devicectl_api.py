import json

import pytest
from django.urls import reverse

import django_devicectl.models as models


def test_create_vlan(db, account_objects):
    client = account_objects.api_client
    facility = account_objects.facility
    org = account_objects.org

    response = client.post(
        reverse("devicectl_api:vlan-list", args=(org.slug,)),
        json.dumps(
            {
                "facility": facility.id,
                "name": "Test Vlan",
                "vlan": 12,
                "slug": "test_vlan",
                "description": "Sample Vlan test",
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["facility_name"] == facility.name
    assert data[0]["facility_slug"] == facility.slug
    assert models.Vlan.objects.get(id=data[0]["id"])


def test_retrieve_vlan(db, account_objects):
    client = account_objects.api_client
    org = account_objects.org
    facility = account_objects.facility

    vlan = models.Vlan(
        instance=account_objects.devicectl_instance,
        facility=account_objects.facility,
        name="Test Vlan",
        vlan=12,
        slug="test_vlan",
        description="Sample Vlan test",
    )
    vlan.save()

    response = client.get(
        reverse(
            "devicectl_api:vlan-detail",
            args=(org.slug, vlan.id),
        ),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == vlan.name
    assert data[0]["slug"] == vlan.slug
    assert data[0]["description"] == vlan.description
    assert data[0]["facility_name"] == facility.name
    assert data[0]["facility_slug"] == facility.slug
    assert models.Vlan.objects.get(id=data[0]["id"])


def test_list_vlans(db, account_objects):
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

    response = client.get(
        reverse(
            "devicectl_api:vlan-list",
            args=(org.slug,),
        ),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == vlan.name
    assert data[0]["slug"] == vlan.slug
    assert data[0]["description"] == vlan.description
    assert data[0]["facility_name"] == facility.name
    assert data[0]["facility_slug"] == facility.slug
    assert models.Vlan.objects.get(id=data[0]["id"])


def test_delete_vlan(db, account_objects):
    client = account_objects.api_client
    org = account_objects.org

    vlan = models.Vlan(
        instance=account_objects.devicectl_instance,
        facility=account_objects.facility,
        name="Test Vlan",
        vlan=12,
        slug="test_vlan",
        description="Sample Vlan test",
    )
    vlan.save()

    response = client.delete(
        reverse(
            "devicectl_api:vlan-detail",
            args=(org.slug, vlan.id),
        ),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1

    with pytest.raises(models.Vlan.DoesNotExist):
        models.Vlan.objects.get(id=data[0]["id"])


def test_facility_list_vlans(db, account_objects):
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

    response = client.get(
        reverse(
            "devicectl_api:facility-vlans",
            args=(
                org.slug,
                facility.slug,
            ),
        ),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == vlan.name
    assert data[0]["slug"] == vlan.slug
    assert data[0]["description"] == vlan.description
    assert data[0]["facility_name"] == facility.name
    assert data[0]["facility_slug"] == facility.slug
    assert models.Vlan.objects.get(id=data[0]["id"])


def test_create_device_metric(db, account_objects):
    client = account_objects.api_client
    org = account_objects.org
    device = account_objects.device
    physical_ports = account_objects.physical_ports
    assert len(physical_ports) > 0

    device_metrics = {
        "ceos00": {
            "optics": [
                {
                    "Ethernet1": {
                        "physical_channels": {
                            "channel": [
                                {
                                    "index": 0,
                                    "state": {
                                        "input_power": {
                                            "avg": -2.9,
                                            "max": -2.8,
                                            "min": -3.1,
                                            "instant": -3.0,
                                        },
                                        "output_power": {
                                            "avg": 1.7,
                                            "max": 1.9,
                                            "min": 1.6,
                                            "instant": 1.8,
                                        },
                                        "laser_bias_current": {
                                            "avg": 9.7,
                                            "max": 9.9,
                                            "min": 9.6,
                                            "instant": 9.8,
                                        },
                                    },
                                }
                            ]
                        }
                    },
                    "Ethernet2": {
                        "physical_channels": {
                            "channel": [
                                {
                                    "index": 0,
                                    "state": {
                                        "input_power": {
                                            "avg": -2.4,
                                            "max": -2.3,
                                            "min": -2.6,
                                            "instant": -2.5,
                                        },
                                        "output_power": {
                                            "avg": 1.6,
                                            "max": 1.7,
                                            "min": 1.4,
                                            "instant": 1.5,
                                        },
                                        "laser_bias_current": {
                                            "avg": 10.1,
                                            "max": 10.3,
                                            "min": 9.9,
                                            "instant": 10.2,
                                        },
                                    },
                                }
                            ]
                        }
                    },
                }
            ],
            "interfaces_counters": [
                {
                    "Ethernet1": {
                        "rx_errors": 0,
                        "rx_octets": 27714716,
                        "tx_errors": 0,
                        "tx_octets": 8732,
                        "rx_discards": 0,
                        "tx_discards": 0,
                        "rx_unicast_packets": 0,
                        "tx_unicast_packets": 0,
                        "rx_broadcast_packets": 0,
                        "rx_multicast_packets": 216268,
                        "tx_broadcast_packets": 0,
                        "tx_multicast_packets": 118,
                    },
                    "Ethernet2": {
                        "rx_errors": 0,
                        "rx_octets": 2828496,
                        "tx_errors": 0,
                        "tx_octets": 8658,
                        "rx_discards": 0,
                        "tx_discards": 0,
                        "rx_unicast_packets": 0,
                        "tx_unicast_packets": 0,
                        "rx_broadcast_packets": 0,
                        "rx_multicast_packets": 13942,
                        "tx_broadcast_packets": 0,
                        "tx_multicast_packets": 117,
                    },
                    "Management0": {
                        "rx_errors": 0,
                        "rx_octets": 29056873,
                        "tx_errors": 0,
                        "tx_octets": 4783600,
                        "rx_discards": 0,
                        "tx_discards": 0,
                        "rx_unicast_packets": 153442,
                        "tx_unicast_packets": 28444,
                        "rx_broadcast_packets": 0,
                        "rx_multicast_packets": 0,
                        "tx_broadcast_packets": 0,
                        "tx_multicast_packets": 0,
                    },
                }
            ],
        }
    }

    response = client.post(
        reverse("devicectl_api:device-metric", args=(org.slug, device.id)),
        json.dumps(
            {
                "data": device_metrics,
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 201
    data = response.json()["data"]
    assert len(data) == 1
    assert data[0] == {
        "ceos00.optics.0.Ethernet1.physical_channels.channel.0.index": 0,
        "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.input_power.avg": -2.9,
        "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.input_power.max": -2.8,
        "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.input_power.min": -3.1,
        "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.input_power.instant": -3.0,
        "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.output_power.avg": 1.7,
        "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.output_power.max": 1.9,
        "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.output_power.min": 1.6,
        "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.output_power.instant": 1.8,
        "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.laser_bias_current.avg": 9.7,
        "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.laser_bias_current.max": 9.9,
        "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.laser_bias_current.min": 9.6,
        "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.laser_bias_current.instant": 9.8,
        "ceos00.optics.0.Ethernet2.physical_channels.channel.0.index": 0,
        "ceos00.optics.0.Ethernet2.physical_channels.channel.0.state.input_power.avg": -2.4,
        "ceos00.optics.0.Ethernet2.physical_channels.channel.0.state.input_power.max": -2.3,
        "ceos00.optics.0.Ethernet2.physical_channels.channel.0.state.input_power.min": -2.6,
        "ceos00.optics.0.Ethernet2.physical_channels.channel.0.state.input_power.instant": -2.5,
        "ceos00.optics.0.Ethernet2.physical_channels.channel.0.state.output_power.avg": 1.6,
        "ceos00.optics.0.Ethernet2.physical_channels.channel.0.state.output_power.max": 1.7,
        "ceos00.optics.0.Ethernet2.physical_channels.channel.0.state.output_power.min": 1.4,
        "ceos00.optics.0.Ethernet2.physical_channels.channel.0.state.output_power.instant": 1.5,
        "ceos00.optics.0.Ethernet2.physical_channels.channel.0.state.laser_bias_current.avg": 10.1,
        "ceos00.optics.0.Ethernet2.physical_channels.channel.0.state.laser_bias_current.max": 10.3,
        "ceos00.optics.0.Ethernet2.physical_channels.channel.0.state.laser_bias_current.min": 9.9,
        "ceos00.optics.0.Ethernet2.physical_channels.channel.0.state.laser_bias_current.instant": 10.2,
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
        "ceos00.interfaces_counters.0.Ethernet2.rx_errors": 0,
        "ceos00.interfaces_counters.0.Ethernet2.rx_octets": 2828496,
        "ceos00.interfaces_counters.0.Ethernet2.tx_errors": 0,
        "ceos00.interfaces_counters.0.Ethernet2.tx_octets": 8658,
        "ceos00.interfaces_counters.0.Ethernet2.rx_discards": 0,
        "ceos00.interfaces_counters.0.Ethernet2.tx_discards": 0,
        "ceos00.interfaces_counters.0.Ethernet2.rx_unicast_packets": 0,
        "ceos00.interfaces_counters.0.Ethernet2.tx_unicast_packets": 0,
        "ceos00.interfaces_counters.0.Ethernet2.rx_broadcast_packets": 0,
        "ceos00.interfaces_counters.0.Ethernet2.rx_multicast_packets": 13942,
        "ceos00.interfaces_counters.0.Ethernet2.tx_broadcast_packets": 0,
        "ceos00.interfaces_counters.0.Ethernet2.tx_multicast_packets": 117,
        "ceos00.interfaces_counters.0.Management0.rx_errors": 0,
        "ceos00.interfaces_counters.0.Management0.rx_octets": 29056873,
        "ceos00.interfaces_counters.0.Management0.tx_errors": 0,
        "ceos00.interfaces_counters.0.Management0.tx_octets": 4783600,
        "ceos00.interfaces_counters.0.Management0.rx_discards": 0,
        "ceos00.interfaces_counters.0.Management0.tx_discards": 0,
        "ceos00.interfaces_counters.0.Management0.rx_unicast_packets": 153442,
        "ceos00.interfaces_counters.0.Management0.tx_unicast_packets": 28444,
        "ceos00.interfaces_counters.0.Management0.rx_broadcast_packets": 0,
        "ceos00.interfaces_counters.0.Management0.rx_multicast_packets": 0,
        "ceos00.interfaces_counters.0.Management0.tx_broadcast_packets": 0,
        "ceos00.interfaces_counters.0.Management0.tx_multicast_packets": 0,
    }

    for physical_port in physical_ports:
        physical_port_stats = models.PhysicalPortStats.objects.get(
            physical_port=physical_port
        )
        assert physical_port_stats.data.get("device_metrics").get("metric") == {
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
        }
