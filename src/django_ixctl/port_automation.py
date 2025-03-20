"""
Functions to help facilitate validation during port provisioning
process and port automation.
"""

import fullctl.service_bridge.devicectl as devicectl
import fullctl.service_bridge.pdbctl as pdbctl
import structlog

import django_ixctl.models.port_automation_tasks as port_automation_tasks
from django_ixctl.models.ixctl import InternetExchange, InternetExchangeMember
from django_ixctl.schema import IXLanConfig

logger = structlog.get_logger(__name__)

__all__ = [
    "get_ix_lan_config",
    "handle_port_assignment",
    "create_device_port",
    "resize_member_port",
    "lag_increase_ports",
    "lag_decrease_ports",
    "unassign_port",
    "sync_ip_addresses",
]


def handle_port_assignment(
    intent: str,
    port_set: list[int],
    member: int | InternetExchangeMember,
    meta: dict | None = None,
) -> devicectl.Port:
    if isinstance(member, int):
        member = InternetExchangeMember.objects.get(pk=member)

    if not port_set or not intent:
        # no port set, no port configuration changes
        return

    if meta is None:
        meta = {}

    if intent == "create":
        return create_device_port(member, port_set, meta=meta)

    if intent == "resize":
        return resize_member_port(member, port_set, meta=meta)

    if intent == "lag-increase":
        return lag_increase_ports(member, port_set, meta=meta)

    if intent == "lag-decrease":
        return lag_decrease_ports(member, port_set, meta=meta)

    if intent == "unassign":
        return unassign_port(member, meta=meta)

    raise ValueError(f"Invalid port configuration intent: {intent}")


def create_device_port(
    member: int | InternetExchangeMember,
    physical_ports: list[int],
    meta: dict | None = None,
    save: bool = True,
) -> devicectl.Port:
    """
    Will call devicectl.Port().create_device_port() with the appropriate
    arguments.

    Will validate that the member currently has no port set. If a port is
    set a value error will be raised.

    This means set the port to None before calling this function.

    Arguments:

    - member: InternetExchangeMember object or ID
    - physical_ports: list of physical ports to be used for the port-channel, by id
    - save: whether to save the member after assigning the port
    """

    if isinstance(member, int):
        member = InternetExchangeMember.objects.get(pk=member)

    if member.port:
        raise ValueError("Member already has a port set")

    org = member.org

    # TODO <sergio>: check customer name pattern
    # and it should not be hardcoded here
    port_name = f"PortChannel-{member.id}"

    port = devicectl.Port().create_device_port(
        org_slug=org.slug,
        name=port_name,
        ports=physical_ports,
    )

    member.port = port["id"]

    if save:
        member.save()

    port_automation_tasks.MemberPortUpdate.create_task(
        org,
        member.id,
        meta=meta,
        physical_ports=physical_ports,
        port=port["id"],
    )

    return port


def resize_member_port(
    member: int | InternetExchangeMember,
    physical_ports: list[str],
    meta: dict | None = None,
    save: bool = True,
) -> devicectl.Port:
    """
    call create_device_port with the new physical_ports.
    """

    if isinstance(member, int):
        member = InternetExchangeMember.objects.get(pk=member)

    if member.port:
        member.port = None

    port = create_device_port(member, physical_ports)

    member.port = port["id"]

    if save:
        member.save()

    return port


def lag_increase_ports(
    member: int | InternetExchangeMember,
    physical_ports: list[int],
    meta: dict | None = None,
):
    """
    Will call devicectl.PhysicalPort.assign() on each new physical port
    """

    if isinstance(member, int):
        member = InternetExchangeMember.objects.get(pk=member)

    current_physical_ports = member.physical_ports

    # get new ports via difference
    new_physical_ports = list(set(physical_ports) - set(current_physical_ports))
    # get ids from member.port.object.physical_ports
    # by comparing ids

    for _id in new_physical_ports:
        devicectl.PhysicalPort().assign(_id, int(member.port))


def lag_decrease_ports(
    member: int | InternetExchangeMember,
    physical_ports: list[int],
    meta: dict | None = None,
):
    """
    Will call devicectl.PhysicalPort.unassign() on each physical port
    that is not in the new list of physical_ports
    """

    if isinstance(member, int):
        member = InternetExchangeMember.objects.get(pk=member)

    current_physical_ports = member.physical_ports

    # get ports to remove via difference
    remove_physical_ports = list(set(current_physical_ports) - set(physical_ports))

    # get ids from member.port.object.physical_ports
    # by comparing ids

    for _id in remove_physical_ports:
        devicectl.PhysicalPort().unassign(_id, int(member.port))


def unassign_port(
    member: int | InternetExchangeMember,
    meta: dict | None = None,
    save: bool = True,
) -> None:
    """
    Will unassign the port from the member.
    """

    for _id in member.physical_ports:
        devicectl.PhysicalPort().unassign(_id, int(member.port))

    member.port = None

    if save:
        member.save()

    port_automation_tasks.MemberPortUpdate.create_task(
        member.org,
        member.id,
        meta=meta,
        port=None,
    )


def sync_ip_addresses(member: int | InternetExchangeMember):
    """
    Will call devicectl.VirtualPort().set_ip_addresses() with the
    appropriate IP addresses for the member.

    Will retrieve prefix lengths from the IXLanConfig for the
    member's InternetExchange.

    Ip addresses are sent as ip interfaces with the prefix length
    set.

    If no prefix lengths are found, the ip addresses are sent with
    a /32 or /128 prefix length.

    Arguments:

    - member: InternetExchangeMember object or ID
    """

    if isinstance(member, int):
        member = InternetExchangeMember.objects.get(pk=member)

    try:
        ixlan_config = get_ix_lan_config(member.ix)

        # set ipaddr4 from member.ipaddr4 with prefix length
        # from ixlan_config

        if member.ipaddr4:
            try:
                ip4_prefix = ixlan_config.get_ip4_prefixes()[0]
                ipaddr4 = f"{member.ipaddr4}/{ip4_prefix.prefixlen}"
            except IndexError:
                ipaddr4 = f"{member.ipaddr4}/32"
        else:
            ipaddr4 = None

        # set ipaddr6 from member.ipaddr6 with prefix length
        # from ixlan_config

        if member.ipaddr6:
            try:
                ip6_prefix = ixlan_config.get_ip6_prefixes()[0]
                ipaddr6 = f"{member.ipaddr6}/{ip6_prefix.prefixlen}"
            except IndexError:
                ipaddr6 = f"{member.ipaddr6}/128"
        else:
            ipaddr6 = None

        devicectl.VirtualPort().set_ip_addresses(
            int(member.port.object.virtual_port),
            ipaddr4,
            ipaddr6,
        )
    except Exception as exc:
        logger.error(
            "Failed to set IP addresses on virtual port",
            member=member.id,
            port=member.port.id,
            ipaddr4=member.ipaddr4,
            ipaddr6=member.ipaddr6,
            error=exc,
        )


def get_ix_lan_config(ix: int | InternetExchange) -> IXLanConfig:
    """
    Get the IXLanConfig for a given InternetExchange object (or ID)
    """

    if isinstance(ix, int):
        ix = InternetExchange.objects.get(pk=ix)

    if not isinstance(ix, InternetExchange):
        raise ValueError("ix must be an InternetExchange object or ID")

    config = IXLanConfig(mtu=ix.mtu)

    for prefix in ix.prefixes.all():
        config.prefixes.append(str(prefix.prefix))

    if (not ix.mtu or not ix.prefixes) and ix.pdb_id:
        # attempt to get from peeringdb

        if not config.mtu:
            pdb_ixlan = pdbctl.InternetExchange().first(id=ix.pdb_id)
            if pdb_ixlan:
                config.mtu = pdb_ixlan.mtu

        if not config.prefixes:
            pdb_prefixes = pdbctl.IXLanPrefix().objects(ix=ix.pdb_id)
            for prefix in pdb_prefixes:
                config.prefixes.append(prefix.prefix)

    return config
