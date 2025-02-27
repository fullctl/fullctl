import ipaddress
import traceback

import fullctl.service_bridge.netbox as netbox
import structlog
from django.utils.translation import gettext_lazy as _
from fullctl.django.models.concrete.service_bridge import service_bridge_action
from fullctl.service_bridge.context import service_bridge_context

import django_devicectl.models.devicectl as models

# TODO: work around to deal with pagination for now
# Needs to be fixed in fullctl service bridge client to naturally
# support pagination arguments
NETBOX_PAGE_LIMIT = 999999

log = structlog.get_logger("django")


@service_bridge_action("netbox_push_device_loc", _("Netbox: update device location"))
def push_device_loc(action, device):
    """
    Push handler that pushes a device location (facility/site) change to netbox
    """

    # this action only works on push
    if action != "push":
        return

    # device main reference source is not netbox
    # TODO: support as secondary source?
    if device.reference_source != "netbox":
        return

    # device no longer assigned to a facility
    if not device.facility_id:
        # TODO: netbox does not allow a device not connected to a siteni
        # what to do here?
        # netbox.Device().partial_update(device.reference.object, {"site": ""})
        return
    facility = device.facility

    # site exists in netbox?
    site = netbox.Site().first(cf_devicectl_id=facility.id)

    if site:
        # assign device to site in netbox
        netbox.Device().partial_update(device.reference.object, {"site": str(site.id)})


@service_bridge_action(
    "netbox_pull_mgmt_ips", _("Netbox: retrieve management ip-addresses")
)
def pull_device_mgmt_ips(action, device):
    """
    Pull handler that pulls device management pimary ip addresses
    from netbox

    Note: this expensive and will significantly slow down API reads for /device
    This is not needed if netbox is set up to automatically push to devicectl
    """

    # this action only works on pull
    if action != "pull":
        return

    if device.reference_source != "netbox":
        return

    netbox_device = device.reference.object

    if not netbox_device:
        return

    if netbox_device.primary_ip4:
        device.set_management_ip_address(netbox_device.primary_ip4.address)

    if netbox_device.primary_ip6:
        device.set_management_ip_address(netbox_device.primary_ip6.address)

    pull_interfaces(device)


def sync_custom_fields():
    """
    Make sure the necessary custom fields exist in netbox
    """

    netbox.CustomField().sync(
        [
            {
                # netbox 1.3.6
                "name": "devicectl_id",
                # netbox 1.4.1
                "slug": "devicectl_id",
                "label": "deviceCtl ID",
                # v3
                "content_types": ["dcim.site"],
                # v4
                "object_types": ["dcim.site"],
                "type": "integer",
                "description": "deviceCtl reference id",
                "required": False,
            },
        ]
    )


def sync_tags(netbox_object, devicectl_object):
    """
    Will transfer the tags from a netbox object to a devicectl object

    Requires the devicectl model to have a `meta` JSON field

    Will return True if the tags have changed, False if not
    """

    if not netbox_object.tags:
        return False

    if not devicectl_object._meta.get_field("meta"):
        return False

    tags = sorted([tag["slug"] for tag in netbox_object.tags])

    if tags != devicectl_object.meta.get("tags", []):
        devicectl_object.meta["tags"] = tags
        return True

    return False


def pull_ip_addresses(virtual_port):
    """
    Pull ip addresses into port infos from netbox for the specified virtualport
    """

    ip4 = None
    ip6 = None

    for netbox_ip in netbox.IPAddress().objects(limit=NETBOX_PAGE_LIMIT):
        if ip4 and ip6:
            break

        if str(netbox_ip.assigned_object_id) != str(virtual_port.reference):
            continue

        if netbox_ip.family.value == 4:
            ip4 = netbox_ip
        elif netbox_ip.family.value == 6:
            ip6 = netbox_ip

    if ip4:
        virtual_port.port.port_info.ip_address_4 = (ip4.address, str(ip4.id))
    else:
        virtual_port.port.port_info.ip_address_4 = None

    if ip6:
        virtual_port.port.port_info.ip_address_6 = (ip6.address, str(ip6.id))
    else:
        virtual_port.port.port_info.ip_address_6 = None


def interface_is_physical(typ):
    """
    For interfaces that arent marked as logical or virtual in netbox

    Compares the netbox interface type value against a list of
    tokens to determine if we want to pull the interface into devicectl

    If any token is found inside the type identifier of the interface
    devicectl will pull it in and create a physical, logical and virtual port chain
    for it.
    """

    ctx = service_bridge_context.get()
    INTERFACE_PHYSICAL = ctx.get_service_config("netbox", "INTERFACE_PHYSICAL") or []

    for phy_if_name in INTERFACE_PHYSICAL:
        if phy_if_name.lower() in typ.lower():
            return True
    return False


def pull_interfaces(device):
    """
    Pulls interfaces into virtual ports from netbox for the specified devices
    """

    for netbox_if in netbox.Interface().objects(
        device_id=str(device.reference), limit=NETBOX_PAGE_LIMIT
    ):
        # for now only pull virtual and lag  interfaces

        if netbox_if.type.value in ["virtual", "lag"] or interface_is_physical(
            netbox_if.type.value
        ):
            pull_interface(netbox_if, device)


def pull_interface(netbox_if, device):
    """
    Pull virtual or LAG interface from netbox

    Called automatically by `pull_interfaces`
    """

    log.info("[PULL] Netbox interface", name=netbox_if.display, id=netbox_if.id)

    # vlan set
    if netbox_if.untagged_vlan:
        vlan_id = netbox_if.untagged_vlan.vid
    else:
        vlan_id = 0

    try:
        virtual_port = models.VirtualPort.objects.get(
            reference=str(netbox_if.id), logical_port__physical_ports__device=device
        )
    except models.VirtualPort.DoesNotExist:
        if netbox_if.type.value == "virtual":
            logical_port = device.physical_ports.first().logical_port
        elif netbox_if.type.value == "lag":
            logical_port = models.LogicalPort.objects.create(
                name=netbox_if.display,
                instance=device.instance,
            )
            models.PhysicalPort.objects.create(device=device, logical_port=logical_port)
        elif interface_is_physical(netbox_if.type.value):
            if getattr(netbox_if, "lag", None):
                # we dont want to pull in lag interfaces through this
                return

            # interface is physical
            logical_port = models.LogicalPort.objects.create(
                name=netbox_if.display,
                instance=device.instance,
            )
            models.PhysicalPort.objects.create(
                device=device,
                logical_port=logical_port,
                name=netbox_if.display,
                reference=str(netbox_if.id),
            )

        # TODO: what to do for tagged vlans, there could be multiple

        virtual_port = models.VirtualPort.objects.create(
            reference=str(netbox_if.id),
            # setting the vlan id here will automatically create / reference
            # the vlan object via the signal handler
            vlan_id=vlan_id,
            logical_port=logical_port,
            name=netbox_if.display,
        )
    except models.VirtualPort.MultipleObjectsReturned:
        log.error(
            "[PULL] Multiple virtual ports found for netbox interface",
            name=netbox_if.display,
            id=netbox_if.id,
        )
        return
    except Exception as exc:
        log.error(
            "[PULL] Error creating virtual port",
            name=netbox_if.display,
            id=netbox_if.id,
            traceback=traceback.format_exc(),
            exc=exc,
        )
        return

    changed = virtual_port.sync_from_reference(ref_obj=netbox_if) or sync_tags(
        netbox_if, virtual_port
    )

    if vlan_id != virtual_port.vlan_id:
        virtual_port.vlan_id = vlan_id
        changed = True

    if changed:
        virtual_port.save()
        if netbox_if.type.value == "lag":
            virtual_port.logical_port.name = virtual_port.name
            virtual_port.logical_port.description = virtual_port.description
            sync_tags(netbox_if, virtual_port.logical_port)
            virtual_port.logical_port.save()

    try:
        virtual_port.port
    except AttributeError:
        virtual_port.port = models.Port.objects.create(virtual_port=virtual_port)
        virtual_port.save()

    if not virtual_port.port.port_info:
        virtual_port.port.port_info = models.PortInfo.objects.create(
            instance=device.instance
        )
        virtual_port.port.save()

    pull_ip_addresses(virtual_port)


def delete_interfaces(instance):
    """
    Deletes all netbox referenced virtual ports that not longer
    exist as interfaces in netbox
    """

    virtual_port_qset = (
        models.VirtualPort.objects.filter(logical_port__instance=instance)
        .exclude(reference__isnull=True)
        .exclude(reference="")
    )

    references = [virtual_port.reference for virtual_port in virtual_port_qset]

    # delete interfaces that no longer exist in netbox

    qset_remove = (
        models.VirtualPort.objects.filter(logical_port__instance=instance)
        .exclude(reference__in=references)
        .exclude(reference__isnull=True)
    )
    qset_remove.delete()


def pull(org, *args, **kwargs):
    """
    Pull data from netbox
    """
    purge = kwargs.pop("purge", False)

    instance = models.Instance.objects.get(org=org)

    # FIXME allow per organization set up of netbox url / token
    # currently uses globally configured values for both

    references = []
    ctx = service_bridge_context.get()

    DEVICE_ROLE = ctx.get_service_config("netbox", "DEVICE_ROLE")

    roles = [r.lower() for r in DEVICE_ROLE]

    # sync vlans

    sync_vlans(instance)

    # create / update devices from netbox data

    for netbox_device in netbox.Device().objects(limit=NETBOX_PAGE_LIMIT):

        # v3 has role in .device_role
        # v4 has role in .role
        # support both
        role = getattr(
            netbox_device, "device_role", getattr(netbox_device, "role", None)
        )

        # v3 returns role as str
        # v4 returns role as dict (converted to object)
        if not isinstance(role, str):
            role = role.name

        if role and role.lower() not in roles:
            continue

        device, created = models.Device.objects.get_or_create(
            reference=str(netbox_device.id), instance=instance
        )
        log.info(
            f"[PULL] Netbox device {netbox_device.name} {device.reference} ROLE {role} ..."
        )
        references.append(device.reference)
        changed = device.sync_from_reference(ref_obj=netbox_device) or sync_tags(
            netbox_device, device
        )

        if netbox_device.platform:
            platform = netbox_device.platform.slug
            if platform != device.meta.get("platform"):
                device.meta["platform"] = platform
                changed = True

        if changed or created:
            device.save()

        if not device.physical_ports.exists():
            device.setup()

        # pull interfaces

        pull_interfaces(device)

        # assign to facility

        site = netbox.Site().first(id=netbox_device.site.id)

        if site.custom_fields.devicectl_id:
            facility = models.Facility.objects.get(
                instance=instance, id=site.custom_fields.devicectl_id
            )
            device.facility = facility
            device.save()

        if netbox_device.primary_ip4:
            device.set_management_ip_address(netbox_device.primary_ip4.address)

        if netbox_device.primary_ip6:
            device.set_management_ip_address(netbox_device.primary_ip6.address)

    if purge:
        # delete devices that no longer exist in netbox

        qset_remove = (
            models.Device.objects.filter(instance=instance)
            .exclude(reference__in=references)
            .exclude(reference__isnull=True)
        )

        qset_remove.delete()

        delete_interfaces(instance)


def sync_vlans(
    instance: models.Instance,
):
    """
    Pulls all vlans from netbox
    """

    log.info("[PULL] Syncing vlans ...")
    for netbox_vlan in netbox.VLAN().objects(limit=NETBOX_PAGE_LIMIT):

        log.info(
            "[PULL] Netbox vlan",
            name=netbox_vlan.name,
            id=netbox_vlan.id,
            vid=netbox_vlan.vid,
        )
        
        facility = None

        if netbox_vlan.site:

            site = netbox.Site().first(id=netbox_vlan.site.id)

            try:
                facility = models.Facility.objects.get(
                    instance=instance, reference=str(site.custom_fields.devicectl_id)
                )
            except models.Facility.DoesNotExist:
                log.info(
                    f"[PULL] Netbox vlan {netbox_vlan.name} {netbox_vlan.id} no facility found, creating without facility ..."
                )

        vlan, created = models.Vlan.objects.get_or_create(
            reference=str(netbox_vlan.id),
            instance=instance,
            defaults={
                "facility": facility,
            },
        )

        changed = vlan.sync_from_reference(ref_obj=netbox_vlan)

        if changed or created:
            log.info(f"[PULL] Netbox vlan {netbox_vlan.name} {vlan.reference} ...")
            vlan.save()


### PUSH


def push(org, *args, **kwargs):
    """
    Push data to netbox
    """

    purge = kwargs.pop("purge", False)

    # make sure required custom fields exist on the netbox side

    sync_custom_fields()

    if kwargs.get("full_sync"):
        push_full_sync(org.instance)

    # preload netbox data

    netbox_sites = [fac for fac in netbox.Site().objects(limit=NETBOX_PAGE_LIMIT)]

    # sync devicectl facility -> netbox site

    for fac in (
        models.Facility.objects.filter(instance__org=org)
        .exclude(slug="pdb")
        .exclude(slug="peerctl")
    ):
        exists = False

        for netbox_site in netbox_sites:
            # check if id match exists
            if netbox_site.custom_fields.devicectl_id == fac.id:
                exists = netbox_site
                break

        if not exists:
            # check if slug match exists
            for netbox_site in netbox_sites:
                if netbox_site.slug.lower() == fac.slug.lower():
                    exists = netbox_site
                    break

        if not exists:
            # site does not exist (searched slug and devicectl reference id matches)
            # create it

            netbox_site = netbox.Site().create(fac.service_bridge_data("netbox"))

        else:
            # site exists (searched slug and devicectl reference id matches)
            # update it

            netbox.Site().update(exists, fac.service_bridge_data("netbox"))

    # delete netbox sites if they no longer exist as facilities in devicectl
    if purge:
        for site in netbox_sites:
            if not site.custom_fields.devicectl_id:
                continue

            if not models.Facility.objects.filter(
                id=site.custom_fields.devicectl_id
            ).exists():
                netbox.Site().destroy(site)


def push_facility(facility):
    """
    Push a facility to netbox as a site

    Args:
        facility: Facility object to push
    """

    # check if site exists in netbox by devicectl id
    site = netbox.Site().first(cf_devicectl_id=facility.id)

    # if not, match by slug
    if not site:
        site = netbox.Site().first(slug=facility.slug)

    # if not match by name
    if not site:
        site = netbox.Site().first(name=facility.name)

    data = {
        "name": facility.name,
        "slug": facility.slug,
        "status": "active",
        "physical_address": facility.address1,
        "latitude": facility.latitude_float,
        "longitude": facility.longitude_float,
        "custom_fields": {"devicectl_id": facility.id},
    }

    if site:
        # update existing site
        netbox.Site().update(site, data)
        log.info("[PUSH] Updated netbox site", site=site, facility=facility)
    else:
        # create new site
        site = netbox.Site().create(data)
        log.info("[PUSH] Created netbox site", site=site, facility=facility)

    return site


def push_require_device_role():

    """
    Will attempt to fetch any matching device role from netbox

    If none are found will create a role from the first element in the list.
    """
    ctx = service_bridge_context.get()
    DEVICE_ROLE = ctx.get_service_config("netbox", "DEVICE_ROLE")

    if not DEVICE_ROLE:
        log.warning(
            "[PUSH] No DEVICE_ROLE set in netbox federation config. Defaulting to 'Router'"
        )
        DEVICE_ROLE = ["Router"]

    for role in DEVICE_ROLE:
        netbox_role = netbox.DeviceRole().first(name=role)

        if netbox_role:
            return netbox_role

    log.info("[PUSH] Creating netbox device role", role=DEVICE_ROLE[0])

    data = netbox.DeviceRole().create(
        {
            "name": DEVICE_ROLE[0],
            "slug": DEVICE_ROLE[0].lower().replace(" ", "_"),
            "color": "ffffff",
        }
    )
    return netbox.DeviceRoleObject(**data)


def push_require_device_type(device_type: str):
    """
    Will attempt to fetch any matching device type from netbox

    If type doesn't exist will create it
    """

    netbox_device_type = netbox.DeviceType().first(model=device_type)

    if not netbox_device_type:
        log.info("[PUSH] Creating netbox device type", type=device_type)
        data = netbox.DeviceType().create(
            {
                "model": device_type,
                "slug": device_type.lower().replace(" ", "_"),
                "manufacturer": push_require_manufacturer().id,
            }
        )
        return netbox.DeviceTypeObject(**data)

    return netbox_device_type


def push_require_manufacturer(manufacturer: str | None = None):
    """
    Will attempt to fetch any matching manufacturer from netbox

    If manufacturer doesn't exist will create it
    """

    if not manufacturer:
        ctx = service_bridge_context.get()
        manufacturer = ctx.get_service_config("netbox", "DEFAULT_MANUFACTURER")
        if not manufacturer:
            log.warning(
                "[PUSH] No manufacturer provided, and no DEFAULT_MANUFACTURER set in netbox federation config. Defaulting to 'Unknown'"
            )
            manufacturer = "Unknown"

    netbox_manufacturer = netbox.Manufacturer().first(name=manufacturer)

    if not netbox_manufacturer:
        log.info("[PUSH] Creating netbox manufacturer", manufacturer=manufacturer)
        data = netbox.Manufacturer().create(
            {"name": manufacturer, "slug": manufacturer.lower().replace(" ", "_")}
        )
        return netbox.ManufacturerObject(**data)

    return netbox_manufacturer


def push_device(device):
    """
    Push a device to netbox

    Args:
        device: Device object to push
    """

    # skip if device has no facility
    if not device.facility:
        log.info("[PUSH] Skipping device without facility", device=device.id)
        return

    # get netbox site for facility
    site = netbox.Site().first(cf_devicectl_id=device.facility.id)
    if not site:
        log.error(
            "[PUSH] Could not find netbox site for facility",
            facility=device.facility.id,
            device=device.id,
        )
        return

    # check if device exists in netbox
    netbox_device = None
    if device.reference:
        netbox_device = netbox.Device().first(id=str(device.reference))

    if not netbox_device:
        # look by site id and device name
        netbox_device = netbox.Device().first(site=site.name, name=device.name)

    data = {
        "name": device.name,
        "site": site.id,
        "status": "active",
        "tags": device.meta.get("tags", []),
        "comments": device.description or "",
    }

    if netbox_device:
        # update existing device
        data["role"] = netbox_device.role.id
        data["device_type"] = netbox_device.device_type.id
        netbox.Device().update(netbox_device, data)
        log.info(
            "[PUSH] Updated netbox device",
            device=device.id,
            netbox_device=netbox_device.id,
        )
    else:
        # set device_role and device_type and manufacturer
        data["role"] = push_require_device_role().id
        data["device_type"] = push_require_device_type(device.type).id

        # create new device
        netbox_device = netbox.DeviceObject(**netbox.Device().create(data))
        log.info(
            "[PUSH] Created netbox device",
            device=device.id,
            netbox_device=netbox_device.id,
        )

    # update reference
    device.reference = str(netbox_device.id)
    device.save()

    return netbox_device


def push_physical_interface(physical_port, netbox_device):
    """
    Push a physical port as an interface to netbox

    Args:
        pophysical_portrt: PhysicalPort object to push
        netbox_device: Netbox device object to attach interface to
    """

    # check if interface exists in netbox
    netbox_interface = None
    if physical_port.reference:
        netbox_interface = netbox.Interface().first(id=str(physical_port.reference))

    # if no match, try by name
    if not netbox_interface:
        netbox_interface = netbox.Interface().first(
            device=netbox_device.name, name=physical_port.name
        )

    ctx = service_bridge_context.get()

    data = {
        "device": netbox_device.id,
        "name": physical_port.name,
        "enabled": True,
        "description": physical_port.description or "",
        "tags": physical_port.meta.get("tags", []),
    }

    if netbox_interface:

        data["type"] = netbox_interface.type.value

        # update existing interface
        netbox.Interface().update(netbox_interface, data)
        log.info(
            "[PUSH] Updated netbox interface",
            interface=physical_port.id,
            netbox_interface=netbox_interface.id,
        )
    else:
        DEFAULT_PHY_TYPE = ctx.get_service_config("netbox", "DEFAULT_PHY_TYPE")

        if not DEFAULT_PHY_TYPE:
            log.warning(
                "No DEFAULT_PHY_TYPE set in netbox federation config. Defaulting to '1000base-t'"
            )
            DEFAULT_PHY_TYPE = "1000base-t"

        data["type"] = DEFAULT_PHY_TYPE

        # create new interface
        netbox_interface = netbox.InterfaceObject(**netbox.Interface().create(data))
        log.info(
            "[PUSH] Created netbox interface",
            interface=physical_port.id,
            netbox_interface=netbox_interface.id,
        )

    # update reference
    physical_port.reference = str(netbox_interface.id)
    physical_port.save()

    # handle IP addresses
    push_interface_ips(physical_port, netbox_interface)

    return netbox_interface


def push_virtual_interface(virtual_port, netbox_device):
    """
    Push a virtual port as an interface to netbox

    Args:
        virtual_port: VirtualPort object to push
        netbox_device: Netbox device object to attach interface to
    """

    # check if interface exists in netbox
    netbox_interface = None
    if virtual_port.reference:
        netbox_interface = netbox.Interface().first(id=str(virtual_port.reference))

    # if no match, try by name
    if not netbox_interface:
        netbox_interface = netbox.Interface().first(
            device=netbox_device.name, name=virtual_port.name
        )

    # determine interface type based on port
    interface_type = "virtual"

    data = {
        "device": netbox_device.id,
        "name": virtual_port.name,
        "type": interface_type,
        "enabled": True,
        "description": virtual_port.description or "",
        "tags": virtual_port.meta.get("tags", []),
    }

    # handle vlan tagging
    if virtual_port.normalized_vlan_id:
        data["untagged_vlan"] = virtual_port.normalized_vlan_id

    if netbox_interface:
        # update existing interface
        netbox.Interface().update(netbox_interface, data)
        log.info(
            "[PUSH] Updated netbox interface",
            interface=virtual_port.id,
            netbox_interface=netbox_interface.id,
        )
    else:
        # create new interface
        netbox_interface = netbox.InterfaceObject(**netbox.Interface().create(data))
        # update reference
        log.info(
            "[PUSH] Created netbox interface",
            interface=virtual_port.id,
            netbox_interface=netbox_interface.id,
        )

    virtual_port.reference = str(netbox_interface.id)
    virtual_port.save()

    # handle IP addresses
    push_interface_ips(virtual_port, netbox_interface)

    return netbox_interface


def push_interface_ips(virtual_port, netbox_interface):
    """
    Push IP addresses for a virtual port to netbox

    Args:
        virtual_port: VirtualPort object containing IPs
        netbox_interface: Netbox interface object to attach IPs to
    """
    try:
        port_info = virtual_port.port.port_info
    except AttributeError:
        return

    qset = models.IPAddress.objects.filter(port_info=port_info)

    for ip_address in qset:

        # check if IP address exists in netbox
        netbox_ip = None
        if ip_address.reference:
            netbox_ip = netbox.IPAddress().first(id=str(ip_address.reference))

        # if no match try by address
        if not netbox_ip:
            netbox_ip = netbox.IPAddress().first(address=str(ip_address.address))

        data = {
            "address": str(ip_address.address),
            "assigned_object_type": "dcim.interface",
            "assigned_object_id": netbox_interface.id,
            "status": "active",
        }

        if netbox_ip:
            # update existing IP address
            netbox.IPAddress().update(netbox_ip, data)
            log.info(
                "[PUSH] Updated netbox IP address",
                ip_address=ip_address.id,
                netbox_ip=netbox_ip.id,
            )
        else:
            # create new IP address
            netbox_ip = netbox.IPAddressObject(**netbox.IPAddress().create(data))
            # update reference
            log.info(
                "[PUSH] Created netbox IP address",
                ip_address=ip_address.id,
                netbox_ip=netbox_ip.id,
            )

        ip_address.reference = str(netbox_ip.id)
        ip_address.save()


def push_full_sync(instance):
    """
    Push handler that syncs all facilities, devices and interfaces to netbox
    """
    # sync facilities
    for facility in instance.facilities.all():
        try:
            push_facility(facility)
        except Exception as exc:
            log.error(
                "[PUSH] Error pushing facility",
                facility=facility.id,
                traceback=traceback.format_exc(),
                exc=exc,
            )

    # sync devices
    for device in instance.devices.exclude(name__startswith="pdbctl").exclude(
        name__startswith="peerctl"
    ):
        try:
            netbox_device = push_device(device)
            if netbox_device:
                # sync interfaces for device
                for virtual_port in device.virtual_ports.all():
                    try:
                        push_virtual_interface(virtual_port, netbox_device)
                    except Exception as exc:
                        log.error(
                            "[PUSH] Error pushing interface",
                            interface=virtual_port.id,
                            device=device.id,
                            traceback=traceback.format_exc(),
                            exc=exc,
                        )

                for physical_port in device.physical_ports.all():
                    try:
                        push_physical_interface(physical_port, netbox_device)
                    except Exception as exc:
                        log.error(
                            "[PUSH] Error pushing interface",
                            interface=physical_port.id,
                            device=device.id,
                            traceback=traceback.format_exc(),
                            exc=exc,
                        )
        except Exception as exc:
            log.error(
                "[PUSH] Error pushing device",
                device=device.id,
                traceback=traceback.format_exc(),
                exc=exc,
            )
