from collections.abc import Iterable

from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction
from django.db.models import Q
from django.utils.translation import gettext_lazy as _
from fullctl.django.rest.decorators import serializer_registry
from fullctl.django.rest.serializers import ModelSerializer
from rest_framework import serializers

import django_devicectl.models.devicectl as models
from django_devicectl.rest.serializers.devicectl import Metric

Serializers, register = serializer_registry()


@register
class Facility(ModelSerializer):
    org_id = serializers.SerializerMethodField()

    class Meta:
        model = models.Facility
        fields = [
            "id",
            "name",
            "slug",
            "reference",
            "reference_is_sot",
            "instance",
            "org_id",
        ]

    def get_org_id(self, device):
        return device.instance.org.permission_id


@register
class Device(ModelSerializer):
    org_id = serializers.SerializerMethodField()
    facility_slug = serializers.SerializerMethodField()

    class Meta:
        model = models.Device
        fields = [
            "id",
            "name",
            "display_name",
            "reference",
            "reference_is_sot",
            "description",
            "status",
            "type",
            "instance",
            "org_id",
            "facility_id",
            "facility_slug",
        ]

    def get_org_id(self, device):
        return device.instance.org.permission_id

    def get_facility_slug(self, device):
        try:
            return device.facility.slug
        except AttributeError:
            # not assigned to facility
            return None


@register
class DeviceOperationalStatus(ModelSerializer):
    status = serializers.ChoiceField(choices=("ok", "error"))

    class Meta:
        model = models.DeviceOperationalStatus
        fields = [
            "id",
            "device",
            "status",
            "error_message",
            "event",
            "url_current",
            "url_reference",
            "config_current",
            "config_reference",
        ]

    def _save(self):
        """
        When saving a device operational status, we need to either create
        or update the device's operational status relation.
        """

        validated_data = self.validated_data
        device = validated_data["device"]
        status = validated_data["status"]
        error_message = validated_data.get("error_message")
        event = validated_data.get("event")
        url_current = validated_data.get("url_current")
        url_reference = validated_data.get("url_reference")
        config_current = validated_data.get("config_current")
        config_reference = validated_data.get("config_reference")

        try:
            device_operational_status = models.DeviceOperationalStatus.objects.get(
                device=device
            )
            device_operational_status.status = status
            device_operational_status.error_message = error_message
            device_operational_status.event = event
            device_operational_status.url_current = url_current
            device_operational_status.url_reference = url_reference
            device_operational_status.config_current = config_current
            device_operational_status.config_reference = config_reference
            device_operational_status.save()
        except ObjectDoesNotExist:
            device_operational_status = models.DeviceOperationalStatus.objects.create(
                device=device,
                status=status,
                error_message=error_message,
                event=event,
                url_current=url_current,
                url_reference=url_reference,
                config_current=config_current,
                config_reference=config_reference,
            )

        return device_operational_status


@register
class DeviceRefereeReport(ModelSerializer):
    class Meta:
        model = models.DeviceRefereeReport
        fields = [
            "id",
            "device",
            "report",
        ]


@register
class Port(ModelSerializer):
    org_id = serializers.SerializerMethodField()

    ip_address_4 = serializers.CharField(
        read_only=True, source="port_info.ip_address_4"
    )
    ip_address_6 = serializers.CharField(
        read_only=True, source="port_info.ip_address_6"
    )
    is_management = serializers.BooleanField(
        read_only=True, source="port_info.is_management"
    )
    logical_port_name = serializers.SerializerMethodField()
    virtual_port_description = serializers.SerializerMethodField()
    virtual_port_name = serializers.SerializerMethodField()
    virtual_port_macaddr_set = serializers.ListSerializer(
        child=serializers.CharField(),
        read_only=True,
        source="port_info.macaddr_set",
    )
    device = serializers.SerializerMethodField()
    physical_ports = serializers.SerializerMethodField()

    class Meta:
        model = models.Port
        fields = [
            "id",
            "org_id",
            "virtual_port",
            "port_info",
            "display_name",
            "device_id",
            "device_name",
            "device",
            "name",
            "ip_address_4",
            "ip_address_6",
            "is_management",
            "logical_port_name",
            "virtual_port_name",
            "virtual_port_description",
            "virtual_port_macaddr_set",
            "physical_ports",
        ]

    def get_org_id(self, port):
        return port.org.permission_id

    def get_logical_port_name(self, port):
        return port.virtual_port.logical_port.name

    def get_virtual_port_name(self, port):
        return port.virtual_port.name

    def get_virtual_port_description(self, port):
        return port.virtual_port.description

    def get_device(self, port):
        if "device" in self.context.get("joins", []):
            # device from preloaded cache
            device = self.devices.get(port.device_id)

            if not device:
                return None

            # device.facility from preloaded cache
            device.facility = self.facilities.get(device.facility_id)

            return Device(instance=device).data
        return None

    def get_physical_ports(self, port):
        if "physical_ports" in self.context.get("joins", []):
            physical_ports = port.virtual_port.physical_ports
            if not physical_ports:
                return None

            return PhysicalPort(instance=physical_ports, many=True).data
        return None

    @property
    def devices(self):
        """
        Preloads and caches all devices needed to render device relationships
        """
        if not hasattr(self, "_devices"):
            ports = self.instance
            if not isinstance(ports, Iterable):
                ports = [ports]

            self._devices = {
                device.id: device
                for device in models.Device.objects.filter(
                    id__in=[port.device_id for port in ports]
                )
            }
        return self._devices

    @property
    def facilities(self):
        """
        Preloads and caches all facilities needed to render device relationships
        """
        if not hasattr(self, "_facilities"):
            ports = self.instance
            if not isinstance(ports, Iterable):
                ports = [ports]

            self._facilities = {
                facility.id: facility
                for facility in models.Facility.objects.filter(
                    id__in=[
                        self.devices.get(port.device_id).facility_id
                        for port in ports
                        if port.device_id
                    ]
                )
            }
        return self._facilities


@register
class PortInfo(ModelSerializer):
    org_id = serializers.SerializerMethodField()
    macaddr_set = serializers.ListSerializer(
        child=serializers.CharField(),
        required=False,
    )
    class Meta:
        model = models.PortInfo
        fields = [
            "id",
            "org_id",
            "port",
            "ip_address_4",
            "ip_address_6",
            "is_management",
            "is_routeserver_peer",
            "speed",
            "display_name",
            "macaddr_set",
        ]

    def get_org_id(self, port_info):
        return port_info.org.permission_id


@register
class IPAddress(ModelSerializer):
    class Meta:
        model = models.IPAddress
        fields = [
            "id",
            "address",
            "instance",
            "reference",
            "reference_is_sot",
            "port_info",
        ]


@register
class VirtualPort(ModelSerializer):
    class Meta:
        model = models.VirtualPort
        fields = [
            "id",
            "logical_port",
            "vlan_id",
            "port",
            "reference",
            "reference_is_sot",
            "name",
            "display_name",
            "description",
        ]
        read_only_fields = ["port"]


@register
class PhysicalPort(ModelSerializer):
    metric = serializers.SerializerMethodField()

    class Meta:
        model = models.PhysicalPort
        fields = [
            "id",
            "name",
            "device_id",
            "device_name",
            "metric",
        ]

    @staticmethod
    def _filter_dict_by_key_substring(input_dict, substring):
        """
        Filters a dictionary to include only the key-value pairs where the key contains a specified substring.

        Args:
        input_dict (dict): The dictionary to filter.
        substring (str): The substring to search for in the keys.

        Returns:
        dict: A new dictionary with only the key-value pairs where the key contains the substring.
        """
        return {key: value for key, value in input_dict.items() if substring in key}

    def get_metric(self, obj):
        try:
            # Get all metrics from this device
            metric = Metric(
                models.DeviceMetric.objects.filter(device=obj.device.id).latest(
                    "created"
                ),
                context={"detailed": True},
            ).data
            # Return only keys with same port name
            return PhysicalPort._filter_dict_by_key_substring(metric, obj.name)
        except models.DeviceMetric.DoesNotExist:
            return {"Warning: ": "No metrics available for this interface."}


@register
class RequestDummyPorts(serializers.Serializer):
    ref_tag = "request_dummy_ports"

    instance = serializers.IntegerField()
    ports = serializers.JSONField()
    name_prefix = serializers.CharField()
    device_type = serializers.CharField()

    class Meta:
        fields = ["ports", "name_prefix", "instance", "device_type"]

    @transaction.atomic
    def create(self, validated_data):
        ports = validated_data["ports"]
        instance = models.Instance.objects.get(id=validated_data["instance"])
        name_prefix = validated_data["name_prefix"]
        device_type = validated_data["device_type"]

        created_ports = []

        for device_id, port_data in ports.items():
            device, _ = models.Device.objects.get_or_create(
                name=f"{name_prefix}:{device_id}",
                instance=instance,
            )
            device.type = device_type
            device.save()
            device.setup()

            if not device.facility:
                facility = models.Facility.objects.filter(
                    name=name_prefix, instance=instance
                ).first()
                if not facility:
                    facility = models.Facility.objects.create(
                        name=name_prefix, instance=instance, slug=name_prefix.lower()
                    )
                device.facility = facility
                device.save()

            for _port in port_data:
                virtual_port, _ = models.VirtualPort.objects.get_or_create(
                    name=f"{name_prefix}:{device_id}:virt:{_port['id']}",
                    logical_port=device.physical_ports.first().logical_port,
                    vlan_id=0,
                )

                port, port_created = models.Port.objects.get_or_create(
                    virtual_port=virtual_port
                )

                if port_created or not port.name:
                    port.name = f"{name_prefix}:{_port['id']}"
                    port.save()

                ip4_incoming = _port.get("ip_address_4")
                ip6_incoming = _port.get("ip_address_6")
                ip4 = None
                ip6 = None

                name_query = (
                    Q(port_info__port__name__startswith=f"{name_prefix}:")
                    | Q(port_info__port__name__startswith="pdb:")
                    | Q(port_info__port__name__startswith="ixctl:")
                )

                if ip4_incoming:
                    ip4 = (
                        models.IPAddress.objects.filter(
                            instance=instance, address=ip4_incoming
                        )
                        .exclude(name_query)
                        .first()
                    )
                if ip6_incoming:
                    ip6 = (
                        models.IPAddress.objects.filter(
                            instance=instance, address=ip6_incoming
                        )
                        .exclude(name_query)
                        .first()
                    )

                try:
                    if ip4:
                        created_ports.append(ip4.port_info.port)
                except ObjectDoesNotExist:
                    pass

                try:
                    if ip6:
                        created_ports.append(ip6.port_info.port)
                except ObjectDoesNotExist:
                    pass

                port.refresh_from_db()

                if port_created or not port.port_info_id:
                    port.port_info = models.PortInfo.objects.create(
                        instance=instance,
                    )
                    port.save()

                if not ip4 and ip4_incoming:
                    port.port_info.ip_address_4 = ip4_incoming

                if not ip6 and ip6_incoming:
                    port.port_info.ip_address_6 = ip6_incoming

                created_ports.append(port)

        return created_ports


class Traffic(serializers.Serializer):
    id = serializers.IntegerField(allow_null=True)
    bps_in = serializers.IntegerField(allow_null=True)
    bps_out = serializers.IntegerField(allow_null=True)
    bps_in_max = serializers.IntegerField(allow_null=True)
    bps_out_max = serializers.IntegerField(allow_null=True)
    timestamp = serializers.IntegerField(allow_null=True)

    class Meta:
        fields = ["id", "bps_in", "bps_out", "bps_in_max", "bps_out_max", "timestamp"]


@register
class PortTraffic(serializers.ListSerializer):
    child = Traffic()

    ref_tag = "port_traffic"


PORT_STATE = (
    ("ok", _("Ok")),
    ("down", _("Down")),
    ("admin_down", _("Admin Down")),
)


@register
class PortStatus(serializers.Serializer):
    ref_tag = "port_status"

    status = serializers.ChoiceField(
        choices=PORT_STATE,
        allow_blank=True,
        allow_null=True,
        required=False,
        default="ok",
    )
