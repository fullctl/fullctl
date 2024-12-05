from django_devicectl.rest.views.common import (
    get_channel_subject,
    get_device_subject,
    get_interface_from_resource,
)


def test_get_interface_from_resource():
    indexed_resource = "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.input_power.instant"
    interface = get_interface_from_resource(indexed_resource)
    assert interface == "Ethernet1"

    indexed_resource = "ceos00.interfaces_counters.0.Ethernet1.tx_multicast_packets"
    interface = get_interface_from_resource(indexed_resource)
    assert interface == "Ethernet1"

    not_indexed_resource = (
        "ceos00.optics.Ethernet1.physical_channels.channel.0.state.input_power.instant"
    )
    interface = get_interface_from_resource(not_indexed_resource)
    assert interface == "Ethernet1"

    not_indexed_resource = "ceos00.interfaces_counters.Ethernet1.tx_multicast_packets"
    interface = get_interface_from_resource(not_indexed_resource)
    assert interface == "Ethernet1"


def test_get_device_subject():
    resource = "ceos00.interfaces_counters.0.Ethernet1.tx_multicast_packets"
    subject = get_device_subject(resource)
    assert subject == "Transmit Multicast Packets"


def test_get_channel_subject():
    resource = "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.input_power.instant"
    subject = get_channel_subject(resource)
    assert subject == "Optical Receive Power"
