from django.conf import settings
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from fullctl.django.models.concrete.tasks import TaskLimitError

import django_devicectl.referee as referee_util
from django_devicectl.models.devicectl import (
    DeviceRefereeReport,
    IPAddress,
    Port,
    PortInfo,
    VirtualPort,
    Vlan,
)
from django_devicectl.models.tasks import RequestPeerctlSync


@receiver(pre_save, sender=IPAddress)
def ip_address_assignment(sender, instance, **kwargs):
    """
    When a new ip address is assigned to a port or
    an existing ip address is moved to a different port
    devicectl needs to let peerctl know that it needs to
    sync its devices and ports from devicectl
    """

    if instance.pk is not None:
        # ip address moved from one port to another ?
        old_instance = IPAddress.objects.get(pk=instance.pk)
        if old_instance.port_info_id != instance.port_info_id:
            try:
                RequestPeerctlSync.create_task(org=instance.instance.org)
            except TaskLimitError:
                pass

    elif instance.port_info_id is not None:
        # new ip address
        try:
            RequestPeerctlSync.create_task(org=instance.instance.org)
        except TaskLimitError:
            pass


@receiver(post_save, sender=VirtualPort)
def auto_create_port(sender, instance, created, **kwargs):
    """
    When a new virtual port is created, create a port
    for it if one does not already exist
    """

    if created:
        port, port_created = Port.objects.get_or_create(virtual_port=instance)
        if port_created:
            port_info = PortInfo.objects.create(instance=instance.logical_port.instance)
            port.port_info = port_info
            port.save()

@receiver(pre_save, sender=VirtualPort)
def auto_create_vlan(sender, instance, **kwargs):
    """
    When a new virtual port is saved and the vlan_id value mismatches
    the vlan_object.vlan or vlan_object isn't set, set the vlan_object
    """
    if not instance.vlan_id:
        return

    vlan_object_exists = instance.vlan_object_id is not None
    vlan_id_mismatch = (
        instance.vlan_object.vlan != instance.vlan_id
        if vlan_object_exists
        else False
    )

    if not vlan_object_exists or vlan_id_mismatch:
        vlan_object, _ = Vlan.objects.get_or_create(
            instance=instance.device.instance,
            vlan=instance.vlan_id,
            facility=instance.facility,
        )
        instance.vlan_object = vlan_object

@receiver(pre_save, sender=DeviceRefereeReport)
def set_report_kind(sender, instance, **kwargs):
    """
    When a new report is created, set the kind of the report
    based on the status of the report
    """

    instance.set_report_kind()


@receiver(post_save, sender=DeviceRefereeReport)
def delete_old_reports(sender, instance, created, **kwargs):
    """
    When a new report is created, delete all old reports based on max
    age
    """

    if created and settings.REFEREE_REPORT_MAX_AGE > 0:
        referee_util.delete_old_reports(
            instance.device, settings.REFEREE_REPORT_MAX_AGE
        )
