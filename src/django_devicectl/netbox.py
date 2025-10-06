import ipaddress
import traceback

import pynetbox
import structlog
from django.utils.translation import gettext_lazy as _
from fullctl.django.models.concrete.service_bridge import service_bridge_action
from fullctl.service_bridge.context import service_bridge_context

import django_devicectl.models.devicectl as models

# Global NetBox API client cache
_netbox_api_cache = {}

# High page limit to reduce pagination requests
NETBOX_PAGE_LIMIT = 999999


def get_netbox_api():
    """Get the configured NetBox API client from service bridge context"""
    ctx = service_bridge_context.get()

    url = ctx.get_service("netbox").service_url
    token = ctx.get_service_config("netbox", "API_TOKEN")

    if not url or not token:
        raise RuntimeError("NetBox URL and token must be configured")

    return pynetbox.api(url, token=token, threading=True)


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
    api = get_netbox_api()
    sites = list(
        api.dcim.sites.filter(cf_devicectl_id=facility.id, limit=NETBOX_PAGE_LIMIT)
    )
    site = sites[0] if sites else None

    if site:
        # assign device to site in netbox
        try:
            device_obj = api.dcim.devices.get(device.reference.object)
            if device_obj:
                device_obj.update({"site": str(site.id)})
        except Exception as exc:
            log.error(
                "Failed to get/update device in netbox",
                device_reference=device.reference.object,
                exc=exc,
            )


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

    api = get_netbox_api()
    field_data = {
        "name": "devicectl_id",
        "slug": "devicectl_id",
        "label": "deviceCtl ID",
        "content_types": ["dcim.site"],
        "object_types": ["dcim.site"],
        "type": "integer",
        "description": "deviceCtl reference id",
        "required": False,
    }

    existing_fields = list(
        api.extras.custom_fields.filter(name="devicectl_id", limit=NETBOX_PAGE_LIMIT)
    )
    if not existing_fields:
        api.extras.custom_fields.create(field_data)


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

    api = get_netbox_api()
    # Filter IP addresses by assigned_object_id to only get IPs for this interface
    log.info(
        "[PULL] Fetching IP addresses for interface",
        interface_name=virtual_port.name,
        interface_ref=virtual_port.reference,
    )

    for netbox_ip in api.ipam.ip_addresses.filter(
        assigned_object_id=str(virtual_port.reference), limit=NETBOX_PAGE_LIMIT
    ):
        if ip4 and ip6:
            break

        # Safety check - ensure the IP is actually assigned to this interface
        if str(netbox_ip.assigned_object_id) != str(virtual_port.reference):
            continue

        log.info(
            "[PULL] Found IP address",
            address=netbox_ip.address,
            family=netbox_ip.family.value,
            interface_ref=virtual_port.reference,
        )

        if netbox_ip.family.value == 4:
            ip4 = netbox_ip
        elif netbox_ip.family.value == 6:
            ip6 = netbox_ip

    if ip4:
        virtual_port.port.port_info.ip_address_4 = (ip4.address, str(ip4.id))
        log.info(
            "[PULL] Assigned IPv4 to interface",
            interface=virtual_port.name,
            address=ip4.address,
        )
    else:
        virtual_port.port.port_info.ip_address_4 = None

    if ip6:
        virtual_port.port.port_info.ip_address_6 = (ip6.address, str(ip6.id))
        log.info(
            "[PULL] Assigned IPv6 to interface",
            interface=virtual_port.name,
            address=ip6.address,
        )
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

    api = get_netbox_api()
    for netbox_if in api.dcim.interfaces.filter(
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

    api = get_netbox_api()
    for netbox_device in api.dcim.devices.all(limit=NETBOX_PAGE_LIMIT):

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

        # Check for facility BEFORE creating/updating device
        try:
            site = api.dcim.sites.get(netbox_device.site.id)
        except Exception as exc:
            log.error(
                "Failed to get site from netbox", site_id=netbox_device.site.id, exc=exc
            )
            site = None

        # Skip devices without a matching facility in devicectl
        if not site or not site.custom_fields.get("devicectl_id"):
            log.info(
                f"[PULL] Skipping device {netbox_device.name} - no matching facility in devicectl",
                site=site.name if site else None,
                devicectl_id=site.custom_fields.get("devicectl_id") if site else None,
            )
            continue

        # Verify facility exists
        try:
            facility = models.Facility.objects.get(
                instance=instance, id=site.custom_fields.get("devicectl_id")
            )
        except models.Facility.DoesNotExist:
            log.info(
                f"[PULL] Skipping device {netbox_device.name} - facility not found in devicectl",
                devicectl_id=site.custom_fields.get("devicectl_id"),
            )
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

        # Set facility now that we know it exists
        device.facility = facility
        if changed or created or not device.facility_id:
            device.save()

        if not device.physical_ports.exists():
            device.setup()

        # pull interfaces

        pull_interfaces(device)

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

    # Retrieve and normalize VLAN role filter configuration (if any)
    ctx = service_bridge_context.get()
    VLAN_ROLE = ctx.get_service_config("netbox", "VLAN_ROLE") or []
    vlan_roles = [r.lower() for r in VLAN_ROLE]

    api = get_netbox_api()
    for netbox_vlan in api.ipam.vlans.all(limit=NETBOX_PAGE_LIMIT):

        vlan_role = None
        # Apply VLAN role filter when configured
        if vlan_roles:
            vlan_role = getattr(netbox_vlan, "role", None)

            # netbox v3 returns role as str, v4 as object/dict (converted to object)
            if vlan_role and not isinstance(vlan_role, str):
                vlan_role = vlan_role.name

            if not vlan_role or vlan_role.lower() not in vlan_roles:
                continue

        log.info(
            "[PULL] Netbox vlan",
            name=netbox_vlan.name,
            id=netbox_vlan.id,
            vid=netbox_vlan.vid,
            role=vlan_role,
        )

        facility = None

        if netbox_vlan.site:

            try:
                site = api.dcim.sites.get(netbox_vlan.site.id)
            except Exception as exc:
                log.error(
                    "Failed to get site from netbox",
                    site_id=netbox_vlan.site.id,
                    exc=exc,
                )
                site = None

            if site:
                try:
                    log.info(
                        "Checking for facility",
                        site=site,
                        id=site.custom_fields.get("devicectl_id"),
                    )
                    facility = models.Facility.objects.get(
                        instance=instance, id=site.custom_fields.get("devicectl_id")
                    )
                except models.Facility.DoesNotExist:
                    log.info(
                        f"[PULL] Netbox vlan {netbox_vlan.name} {netbox_vlan.id} no facility found, creating without facility ..."
                    )

        if custom_fields := netbox_vlan.custom_fields:
            v4_primary = None
            v6_primary = None
            v4_secondaries = []
            v6_secondaries = []

            try:
                v4_primary = custom_fields.get("v4_primary", {}).get("address", None)
            except Exception as exc:
                log.info(
                    f"[PULL] Netbox vlan {netbox_vlan.name} {netbox_vlan.id} malformed v4_primary custom field, creating without one ..."
                )

            try:
                v6_primary = custom_fields.get("v6_primary", {}).get("address", None)
            except Exception as exc:
                log.info(
                    f"[PULL] Netbox vlan {netbox_vlan.name} {netbox_vlan.id} malformed v6_primary custom field, creating without one ..."
                )

            try:
                _v4_secondaries = custom_fields.get("v4_secondaries", None)
                v4_secondaries = [addr["address"] for addr in _v4_secondaries] if _v4_secondaries else []
            except Exception as exc:
                log.info(
                    f"[PULL] Netbox vlan {netbox_vlan.name} {netbox_vlan.id} malformed v4_secondaries custom field, creating without one ..."
                )
                
            try:
                _v6_secondaries = custom_fields.get("v6_secondaries", None)
                v6_secondaries = [addr["address"] for addr in _v6_secondaries] if _v6_secondaries else []
            except Exception as exc:
                log.info(
                    f"[PULL] Netbox vlan {netbox_vlan.name} {netbox_vlan.id} malformed v6_secondaries custom field, creating without one ..."
                )

        vlan, created = models.Vlan.objects.update_or_create(
            reference=str(netbox_vlan.id),
            instance=instance,
            v4_primary=v4_primary,
            v6_primary=v6_primary,
            v4_secondaries=v4_secondaries,
            v6_secondaries=v6_secondaries,
            defaults={
                "facility": facility,
                "vlan": netbox_vlan.vid,
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

    api = get_netbox_api()
    netbox_sites = list(api.dcim.sites.all(limit=NETBOX_PAGE_LIMIT))

    # sync devicectl facility -> netbox site

    for fac in (
        models.Facility.objects.filter(instance__org=org)
        .exclude(slug="pdb")
        .exclude(slug="peerctl")
    ):
        exists = False

        for netbox_site in netbox_sites:
            # check if id match exists
            if netbox_site.custom_fields.get("devicectl_id") == fac.id:
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

            netbox_site = api.dcim.sites.create(fac.service_bridge_data("netbox"))

        else:
            # site exists (searched slug and devicectl reference id matches)
            # update it

            exists.update(fac.service_bridge_data("netbox"))

    # delete netbox sites if they no longer exist as facilities in devicectl
    if purge:
        for site in netbox_sites:
            if not site.custom_fields.get("devicectl_id"):
                continue

            if not models.Facility.objects.filter(
                id=site.custom_fields.get("devicectl_id")
            ).exists():
                site.delete()


def push_facility(facility):
    """
    Push a facility to netbox as a site

    Args:
        facility: Facility object to push
    """

    # check if site exists in netbox by devicectl id
    api = get_netbox_api()
    sites = list(
        api.dcim.sites.filter(cf_devicectl_id=facility.id, limit=NETBOX_PAGE_LIMIT)
    )
    site = sites[0] if sites else None

    # if not, match by slug
    if not site:
        sites = list(api.dcim.sites.filter(slug=facility.slug, limit=NETBOX_PAGE_LIMIT))
        site = sites[0] if sites else None

    # if not match by name
    if not site:
        sites = list(api.dcim.sites.filter(name=facility.name, limit=NETBOX_PAGE_LIMIT))
        site = sites[0] if sites else None

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
        site.update(data)
        log.info("[PUSH] Updated netbox site", site=site, facility=facility)
    else:
        # create new site
        site = api.dcim.sites.create(data)
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

    api = get_netbox_api()
    for role in DEVICE_ROLE:
        roles = list(api.dcim.device_roles.filter(name=role, limit=NETBOX_PAGE_LIMIT))
        netbox_role = roles[0] if roles else None

        if netbox_role:
            return netbox_role

    log.info("[PUSH] Creating netbox device role", role=DEVICE_ROLE[0])

    data = api.dcim.device_roles.create(
        {
            "name": DEVICE_ROLE[0],
            "slug": DEVICE_ROLE[0].lower().replace(" ", "_"),
            "color": "ffffff",
        }
    )
    return data


def push_require_device_type(device_type: str):
    """
    Will attempt to fetch any matching device type from netbox

    If type doesn't exist will create it
    """

    api = get_netbox_api()
    device_types = list(
        api.dcim.device_types.filter(model=device_type, limit=NETBOX_PAGE_LIMIT)
    )
    netbox_device_type = device_types[0] if device_types else None

    if not netbox_device_type:
        log.info("[PUSH] Creating netbox device type", type=device_type)
        data = api.dcim.device_types.create(
            {
                "model": device_type,
                "slug": device_type.lower().replace(" ", "_"),
                "manufacturer": push_require_manufacturer().id,
            }
        )
        return data

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

    api = get_netbox_api()
    manufacturers = list(
        api.dcim.manufacturers.filter(name=manufacturer, limit=NETBOX_PAGE_LIMIT)
    )
    netbox_manufacturer = manufacturers[0] if manufacturers else None

    if not netbox_manufacturer:
        log.info("[PUSH] Creating netbox manufacturer", manufacturer=manufacturer)
        data = api.dcim.manufacturers.create(
            {"name": manufacturer, "slug": manufacturer.lower().replace(" ", "_")}
        )
        return data

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
    api = get_netbox_api()
    sites = list(api.dcim.sites.filter(cf_devicectl_id=device.facility.id))
    site = sites[0] if sites else None
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
        try:
            netbox_device = api.dcim.devices.get(str(device.reference))
        except Exception as exc:
            log.error(
                "Failed to get device from netbox",
                device_reference=device.reference,
                exc=exc,
            )
            netbox_device = None

    if not netbox_device:
        # look by site slug and device name
        devices = list(
            api.dcim.devices.filter(
                site=site.slug, name=device.name, limit=NETBOX_PAGE_LIMIT
            )
        )
        netbox_device = devices[0] if devices else None

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
        netbox_device.update(data)
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
        netbox_device = api.dcim.devices.create(data)
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
    api = get_netbox_api()
    netbox_interface = None
    if physical_port.reference:
        try:
            netbox_interface = api.dcim.interfaces.get(str(physical_port.reference))
        except Exception as exc:
            log.error(
                "Failed to get interface from netbox",
                interface_reference=physical_port.reference,
                exc=exc,
            )
            netbox_interface = None

    # if no match, try by name
    if not netbox_interface:
        interfaces = list(
            api.dcim.interfaces.filter(
                device=netbox_device.name,
                name=physical_port.name,
                limit=NETBOX_PAGE_LIMIT,
            )
        )
        netbox_interface = interfaces[0] if interfaces else None

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
        netbox_interface.update(data)
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
        netbox_interface = api.dcim.interfaces.create(data)
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
    api = get_netbox_api()
    netbox_interface = None
    if virtual_port.reference:
        try:
            netbox_interface = api.dcim.interfaces.get(str(virtual_port.reference))
        except Exception as exc:
            log.error(
                "Failed to get interface from netbox",
                interface_reference=virtual_port.reference,
                exc=exc,
            )
            netbox_interface = None

    # if no match, try by name
    if not netbox_interface:
        interfaces = list(
            api.dcim.interfaces.filter(
                device=netbox_device.name,
                name=virtual_port.name,
                limit=NETBOX_PAGE_LIMIT,
            )
        )
        netbox_interface = interfaces[0] if interfaces else None

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
        netbox_interface.update(data)
        log.info(
            "[PUSH] Updated netbox interface",
            interface=virtual_port.id,
            netbox_interface=netbox_interface.id,
        )
    else:
        # create new interface
        netbox_interface = api.dcim.interfaces.create(data)
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

    api = get_netbox_api()
    for ip_address in qset:

        # check if IP address exists in netbox
        netbox_ip = None
        if ip_address.reference:
            try:
                netbox_ip = api.ipam.ip_addresses.get(str(ip_address.reference))
            except Exception as exc:
                log.error(
                    "Failed to get IP address from netbox",
                    ip_reference=ip_address.reference,
                    exc=exc,
                )
                netbox_ip = None

        # if no match try by address
        if not netbox_ip:
            ips = list(
                api.ipam.ip_addresses.filter(
                    address=str(ip_address.address), limit=NETBOX_PAGE_LIMIT
                )
            )
            netbox_ip = ips[0] if ips else None

        data = {
            "address": str(ip_address.address),
            "assigned_object_type": "dcim.interface",
            "assigned_object_id": netbox_interface.id,
            "status": "active",
        }

        if netbox_ip:
            # update existing IP address
            netbox_ip.update(data)
            log.info(
                "[PUSH] Updated netbox IP address",
                ip_address=ip_address.id,
                netbox_ip=netbox_ip.id,
            )
        else:
            # create new IP address
            netbox_ip = api.ipam.ip_addresses.create(data)
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
