def get_subject_from_resource(resource: str) -> str | None:
    """
    resource (`str`): The resource which looks like
    "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.input_power.instant" or
    "ceos00.interfaces_counters.0.Ethernet1.tx_multicast_packets"
    """
    if "optics" in resource:
        return get_channel_subject(resource)
    elif "interfaces_counters" in resource:
        return get_device_subject(resource)
    return


def get_channel_subject(resource: str) -> str | None:
    """
    resource (`str`): The resource which looks like
    "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.input_power.instant"
    """
    ChannelStates = {
        "input_power.instant": "Optical Receive Power",
        "output_power.instant": "Optical Transmit Power",
        "laser_bias_current.instant": "Laser Bias Current",
    }
    split_resource = resource.split(".")
    key = ".".join(split_resource[-2:])
    return ChannelStates.get(key, None)


def get_device_subject(resource: str) -> str | None:
    """
    resource (`str`): The resource which looks like
    "ceos00.interfaces_counters.0.Ethernet1.tx_multicast_packets"
    """
    DeviceStates = {
        "rx_octets": "Receive Octets",
        "rx_discards": "Receive Discards",
        "rx_errors": "Receive Errors",
        "rx_unicast_packets": "Receive Unicast Packets",
        "rx_multicast_packets": "Receive Multicast Packets",
        "rx_broadcast_packets": "Receive Broadcast Packets",
        "tx_octets": "Transmit Octets",
        "tx_discards": "Transmit Discards",
        "tx_errors": "Transmit Errors",
        "tx_unicast_packets": "Transmit Unicast Packets",
        "tx_multicast_packets": "Transmit Multicast Packets",
        "tx_broadcast_packets": "Transmit Broadcast Packets",
    }
    split_resource = resource.split(".")
    return DeviceStates.get(split_resource[-1], None)


def get_interface_from_resource(resource: str) -> str:
    """
    resource (`str`): The resource which looks like
    "ceos00.optics.0.Ethernet1.physical_channels.channel.0.state.input_power.instant" or
    "ceos00.interfaces_counters.0.Ethernet1.tx_multicast_packets"
    """
    split_resource = resource.split(".")
    if not len(split_resource) > 3:
        return resource

    # The index is added to the metrics if there are more than 1 metrics data
    # If not it is not added
    # e.g. ceos00.optics.0.Ethernet1.physical_channels.channel.0.index being index 0
    # ceos00.optics.1.Ethernet1.physical_channels.channel.1.index being index 1
    index = (
        split_resource.index("optics")
        if "optics" in resource
        else split_resource.index("interfaces_counters")
    )
    if not split_resource[index + 1].isdigit():
        port = split_resource[index + 1]
    else:
        port = split_resource[index + 2]
    return port


def extract_metric_data_from_ports(ports: dict):
    result = []
    for port in ports:
        flat_data = port.get("metric")
        kv = []
        for x, y in flat_data.items():
            if subject := get_subject_from_resource(x):
                kv.append(
                    {
                        "device": port.get("device_name"),
                        "resource": x,
                        "value": y,
                        "interface": get_interface_from_resource(x),
                        "subject": subject,
                    }
                )
        result.extend(kv)
    return result
