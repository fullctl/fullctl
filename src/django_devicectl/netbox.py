import fullctl.service_bridge.netbox as netbox
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from fullctl.django.models.concrete.service_bridge import service_bridge_action
from fullctl.service_bridge.context import service_bridge_context

import django_devicectl.models.devicectl as models

# TODO: work around to deal with pagination for now
# Needs to be fixed in fullctl service bridge client to naturally
# support pagination arguments
NETBOX_PAGE_LIMIT = 999999


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
                "content_types": ["dcim.site"],
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

    for phy_if_name in settings.NETBOX_INTERFACE_PHYSICAL:
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
                device=device, logical_port=logical_port, name=netbox_if.display
            )

        virtual_port = models.VirtualPort.objects.create(
            reference=str(netbox_if.id),
            vlan_id=0,
            logical_port=logical_port,
            name=netbox_if.display,
        )

    changed = virtual_port.sync_from_reference(ref_obj=netbox_if) or sync_tags(
        netbox_if, virtual_port
    )

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

    instance = models.Instance.objects.get(org=org)

    # FIXME allow per organization set up of netbox url / token
    # currently uses globally configured values for both

    references = []
    ctx = service_bridge_context.get()

    DEVICE_ROLE = ctx.get_service_config("netbox", "DEVICE_ROLE")

    roles = [r.lower() for r in DEVICE_ROLE]

    # create / update devices from netbox data

    for netbox_device in netbox.Device().objects(limit=NETBOX_PAGE_LIMIT):
        if netbox_device.device_role.name.lower() not in roles:
            continue

        device, created = models.Device.objects.get_or_create(
            reference=str(netbox_device.id), instance=instance
        )
        print(f"[PULL] Netbox device {netbox_device.name} {device.reference} ...")
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

    # delete devices that no longer exist in netbox

    qset_remove = (
        models.Device.objects.filter(instance=instance)
        .exclude(reference__in=references)
        .exclude(reference__isnull=True)
    )

    qset_remove.delete()

    delete_interfaces(instance)


def push(org, *args, **kwargs):
    """
    Push data to netbox
    """
    # make sure required custom fields exist on the netbox side

    sync_custom_fields()

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
    for site in netbox_sites:
        if not site.custom_fields.devicectl_id:
            continue

        if not models.Facility.objects.filter(
            id=site.custom_fields.devicectl_id
        ).exists():
            netbox.Site().destroy(site)
