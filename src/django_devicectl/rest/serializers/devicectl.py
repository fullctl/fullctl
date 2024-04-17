import json

from django.utils.translation import gettext_lazy as _
from fullctl.django.rest.decorators import serializer_registry
from fullctl.django.rest.serializers import ModelSerializer
from rest_framework import serializers

import django_devicectl.models as models
import django_devicectl.models.tasks as tasks

Serializers, register = serializer_registry()


@register
class Facility(ModelSerializer):
    class Meta:
        model = models.Facility
        fields = [
            "id",
            "name",
            "slug",
            "address1",
            "city",
            "country",
            "floor",
            "suite",
            "zipcode",
            "reference",
            "reference_source",
            "reference_is_sot",
            "reference_ux_url",
            "reference_api_url",
            "instance",
        ]


@register
class FacilityAddDevice(serializers.Serializer):
    device = serializers.IntegerField(help_text=_("Device id"))

    ref_tag = "facility_add_device"

    class Meta:
        fields = ["device"]


@register
class DeviceOperationalStatus(ModelSerializer):
    class Meta:
        model = models.DeviceOperationalStatus
        fields = ["id", "device", "status", "error_message"]


@register
class DeviceConfig(serializers.Serializer):
    id = serializers.IntegerField(help_text=_("Device id"), read_only=True)
    config = serializers.CharField(help_text=_("Device configuration"), read_only=True)
    url = serializers.CharField(
        help_text=_("Device configuration source"),
        read_only=True,
        allow_null=True,
        allow_blank=True,
    )

    ref_tag = "device_config"

    class Meta:
        fields = ["config", "url"]


@register
class DeviceConfigHistory(ModelSerializer):
    class Meta:
        model = models.DeviceConfigHistory
        fields = ["id", "device", "status", "error_message", "created"]


@register
class DeviceRefereeReport(ModelSerializer):
    report_data = serializers.SerializerMethodField()

    class Meta:
        model = models.DeviceRefereeReport
        fields = ["id", "device", "status", "kind", "created", "report_data"]

    def get_report_data(self, report):
        # we only want to include report data on single report serialization
        # and not on list serialization

        if isinstance(self.instance, models.DeviceRefereeReport):
            return json.loads(report.report)


class TagMixin:
    def get_tags(self, obj):
        return obj.meta.get("tags", [])


@register
class DeviceMeta(serializers.Serializer):
    tags = serializers.ListField(
        help_text=_("Device tags"),
        child=serializers.CharField(help_text=_("Device tag")),
        required=False,
    )
    platform = serializers.CharField(help_text=_("Device platform"), required=False)
    firmware_version = serializers.CharField(
        help_text=_("Firmware version"), required=False
    )

    ref_tag = "device_meta"

    class Meta:
        fields = ["tags", "platform", "firmware_version"]


@register
class Device(TagMixin, ModelSerializer):
    facility_name = serializers.SerializerMethodField()
    facility_slug = serializers.SerializerMethodField()

    management_ip_address_4 = serializers.SerializerMethodField()
    management_ip_address_6 = serializers.SerializerMethodField()

    operational_status = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    meta = DeviceMeta(help_text=_("Device meta"), read_only=True)

    class Meta:
        model = models.Device
        fields = [
            "name",
            "display_name",
            "type",
            "facility",
            "facility_name",
            "facility_slug",
            "reference",
            "reference_source",
            "reference_is_sot",
            "reference_ux_url",
            "reference_api_url",
            "description",
            "instance",
            "management_ip_address_4",
            "management_ip_address_6",
            "operational_status",
            "tags",
            "meta",
        ]

    def get_facility_name(self, obj):
        if obj.facility is None:
            return None
        return obj.facility.name

    def get_facility_slug(self, obj):
        if obj.facility is None:
            return None
        return obj.facility.slug

    def get_management_ip_address_4(self, obj):
        port = obj.management_port
        if not port or not port.ip_address_4:
            return None
        return f"{port.ip_address_4}"

    def get_management_ip_address_6(self, obj):
        port = obj.management_port
        if not port or not port.ip_address_6:
            return None
        return f"{port.ip_address_6}"

    def get_operational_status(self, obj):
        try:
            return obj.operational_status.status
        except models.DeviceOperationalStatus.DoesNotExist:
            return "ok"


@register
class PhysicalPort(ModelSerializer):
    class Meta:
        model = models.PhysicalPort
        fields = [
            "device",
            "device_name",
            "name",
            "display_name",
            "logical_port",
            "logical_port_name",
            "description",
        ]


@register
class LogicalPort(TagMixin, ModelSerializer):
    tags = serializers.SerializerMethodField()

    class Meta:
        model = models.LogicalPort
        fields = [
            "name",
            "display_name",
            "trunk",
            "channel",
            "description",
            "instance",
            "tags",
        ]


class InlinePhysicalPort(ModelSerializer):
    class Meta:
        model = models.PhysicalPort
        fields = ["id", "name"]


@register
class Port(ModelSerializer):
    logical_port_name = serializers.SerializerMethodField()
    virtual_port_name = serializers.SerializerMethodField()

    class Meta:
        model = models.Port
        fields = [
            "name",
            "display_name",
            "logical_port_name",
            "virtual_port_name",
            "device_name",
            "device_id",
        ]

    def get_logical_port_name(self, port):
        return port.virtual_port.logical_port.name

    def get_virtual_port_name(self, port):
        return port.virtual_port.name


@register
class VirtualPort(TagMixin, ModelSerializer):
    physical_ports = serializers.SerializerMethodField()
    device = serializers.SerializerMethodField()
    port = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()

    class Meta:
        model = models.VirtualPort
        fields = [
            "name",
            "display_name",
            "logical_port",
            "logical_port_name",
            "device",
            "device_name",
            "physical_ports",
            "vlan_id",
            "port",
            "tags",
        ]

    def get_physical_ports(self, obj):
        return InlinePhysicalPort(obj.physical_ports.all(), many=True).data

    def get_device(self, obj):
        return obj.device.id

    def get_port(self, obj):
        return obj.port.id


@register
class PeeringDBFacility(serializers.Serializer):
    ref_tag = "pdbfacility"

    id = serializers.IntegerField()
    name = serializers.CharField(read_only=True)
    address1 = serializers.CharField(read_only=True)
    country = serializers.CharField(read_only=True)
    zipcode = serializers.CharField(read_only=True)
    city = serializers.CharField(read_only=True)
    suite = serializers.CharField(read_only=True)
    floor = serializers.CharField(read_only=True)
    latidude = serializers.DecimalField(read_only=True, max_digits=9, decimal_places=6)
    longitude = serializers.DecimalField(read_only=True, max_digits=9, decimal_places=6)

    class Meta:
        fields = ["id", "name"]

    def get_router_id(self, obj):
        return obj.ipaddr4 or ""


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
class DeviceTraffic(serializers.ListSerializer):
    child = Traffic()

    ref_tag = "device_traffic"


@register
class DeviceGroupTraffic(serializers.ListSerializer):
    child = Traffic()

    ref_tag = "device_group_traffic"


@register
class PortTraffic(serializers.ListSerializer):
    child = Traffic()

    ref_tag = "port_traffic"

    def save(self):
        try:
            context_model = list(self.context["context_objs"].values())[0].HandleRef.tag
        except IndexError:
            # no valid context models pushed to the serializer
            return

        tasks.UpdateTrafficGraphs.create_task(
            update=self.validated_data,
            org=self.context["org"],
            context_model=context_model,
        )


@register
class PortTrafficMRTGImport(serializers.Serializer):

    """
    Allows importing of port traffic data points using log lines
    from an MRTG log file.

    timestamp bits_in bits_out bits_in_max bits_out_max
    """

    id = serializers.IntegerField(allow_null=True)
    log_lines = serializers.ListField(child=serializers.CharField())

    ref_tag = "port_traffic_mrtg_import"

    class Meta:
        fields = ["id", "log_lines"]

    def validate_log_lines(self, log_lines):
        for line in log_lines:
            try:
                timestamp, bits_in, bits_out, bits_in_max, bits_out_max = line.split()
            except ValueError:
                raise serializers.ValidationError(
                    "Invalid log line format, expected: timestamp bits_in bits_out bits_in_max bits_out_max"
                )

            try:
                timestamp = int(timestamp)
                bits_in = int(bits_in)
                bits_out = int(bits_out)
                bits_in_max = int(bits_in_max)
                bits_out_max = int(bits_out_max)
            except ValueError:
                raise serializers.ValidationError(
                    "Invalid log line format, expected integers"
                )

        return log_lines


@register
class PortTrafficMRTGImportBatch(serializers.ListSerializer):
    child = PortTrafficMRTGImport()
    ref_tag = "port_traffic_mrtg_import_batch"

    def save(self):
        context_model = list(self.context["context_objs"].values())[0].HandleRef.tag

        tasks.UpdateTrafficGraphs.create_task(
            import_mrtg=self.validated_data,
            org=self.context["org"],
            context_model=context_model,
        )
