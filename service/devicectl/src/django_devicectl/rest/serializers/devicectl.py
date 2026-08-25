import json

import django_devicectl.models as models
import django_devicectl.models.tasks as tasks
import structlog
from django.db.models import Prefetch
from django.utils.translation import gettext_lazy as _
from flatten_json import flatten
from netfields.rest_framework import InetAddressField as InetAddressSerializerField
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from fullctl.django.inet.validators import validate_mac_addresses
from fullctl.django.rest.decorators import serializer_registry
from fullctl.django.rest.serializers import ModelSerializer

logger = structlog.getLogger("django_structlog")

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

    @property
    def management_ips(self) -> dict:
        """
        Build a cache of management IPs for all devices being serialized.
        This significantly reduces database queries when serializing many devices.
        """

        # Check if parent already has the cache
        if hasattr(self, "_management_ips"):
            return self._management_ips

        # Initialize the cache on the parent
        self._management_ips = {}

        # Get all device IDs from the parent's instance (which is the queryset)
        if isinstance(self.instance, models.Device):
            device_ids = [self.instance.id]
        else:
            device_ids = [device.id for device in self.instance]

        # Bulk fetch all management port infos with their IPs
        port_infos = (
            models.PortInfo.objects.filter(
                is_management=True,
                port__virtual_port__logical_port__physical_ports__device_id__in=device_ids,
            )
            .prefetch_related(Prefetch("ips", queryset=models.IPAddress.objects.all()))
            .select_related("port__virtual_port__logical_port")
            .prefetch_related("port__virtual_port__logical_port__physical_ports")
            .distinct()
        )

        # Build a mapping from port_info to device_id
        for port_info in port_infos:
            # Find all devices connected to this port_info
            physical_ports = (
                port_info.port.virtual_port.logical_port.physical_ports.all()
            )
            for physical_port in physical_ports:
                device_id = physical_port.device_id

                if device_id in self._management_ips:
                    continue

                ipv4 = None
                ipv6 = None

                # Process IPs - they're already prefetched
                for ip in port_info.ips.all():
                    if ip.address.version == 4 and not ipv4:
                        ipv4 = str(ip.address)
                    elif ip.address.version == 6 and not ipv6:
                        ipv6 = str(ip.address)

                self._management_ips[device_id] = {
                    "ipv4": ipv4,
                    "ipv6": ipv6,
                    "port_info_id": port_info.id,  # for debugging
                }

        return self._management_ips

    def get_facility_name(self, obj):
        if obj.facility is None:
            return None
        return obj.facility.name

    def get_facility_slug(self, obj):
        if obj.facility is None:
            return None
        return obj.facility.slug

    def get_management_ip_address_4(self, obj):
        return self.management_ips.get(obj.id, {}).get("ipv4")

    def get_management_ip_address_6(self, obj):
        return self.management_ips.get(obj.id, {}).get("ipv6")

    def get_operational_status(self, obj):
        try:
            return obj.operational_status.status
        except models.DeviceOperationalStatus.DoesNotExist:
            return "ok"


@register
class PhysicalPort(ModelSerializer):
    metric = serializers.SerializerMethodField()

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
            "metric",
            "size",
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
            # Return only keys with same port name and a dot to match the substring exactly
            return PhysicalPort._filter_dict_by_key_substring(metric, f"{obj.name}.")
        except models.DeviceMetric.DoesNotExist:
            return {"Warning: ": "No metrics available for this interface."}


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
class ACL(ModelSerializer):
    """Serializer for ACL model.

    This serializer transforms AccessControlList model instances
    into JSON format and validates incoming data for creating or
    updating ACL entries.

    Attributes:
    - Meta: Metadata for the serializer, including the model it
    serializes and the fields to include.

    Example:
    ```
    >>> from django_devicectl.models import ACL
    >>> from django_devicectl.rest.serializers.devicectl import ACL as ACLSerializer
    >>> acl = ACL.objects.get(id=1)
    >>> serializer = ACLSerializer(acl)
    >>> print(serializer.data)
    {'name': 'acl_example_1', 'device': 6, 'device_name': 'Demo Device', 'instance': 10, 'grainy': 'acl.33.1130', 'id': 1, 'status': 'ok', 'created': '2024-07-18T14:00:10.446656Z', 'updated': '2024-07-18T14:00:10.446701Z'}

    ```
    """

    class Meta:
        """Meta class for ACL Serializer.

        Attributes:
        - model (ACL): The model that the serializer transforms.
        - fields (list): The fields to include in the serialized output.
        """

        model = models.ACL
        fields = [
            "name",
            "device",
            "device_name",
            "instance",
        ]


@register
class VirtualPort(TagMixin, ModelSerializer):
    physical_ports = serializers.SerializerMethodField()
    device = serializers.SerializerMethodField()
    port = serializers.SerializerMethodField()
    tags = serializers.SerializerMethodField()
    logical_ports_data = LogicalPort(write_only=True, allow_null=True)
    macaddr_set = serializers.ListSerializer(
        child=serializers.CharField(),
        # this needs to be read only for now, since drf doesnt
        # automatically support writable nested serializers
        #
        # use the batch_set_macaddr serializer to set mac addresses
        read_only=True,
        source="port.port_info.macaddr_set",
    )

    class Meta:
        model = models.VirtualPort
        fields = [
            "name",
            "display_name",
            "logical_port",
            "logical_port_name",
            "logical_ports_data",
            "device",
            "device_name",
            "physical_ports",
            "vlan_object",
            "vlan_id",
            "port",
            "tags",
            "acl",
            "acl_name",
            "macaddr_set",
        ]

    def get_acl(self, obj):
        if not obj.acl:
            return None
        return obj.acl.name

    def get_acl_name(self, obj):
        if not obj.acl_name:
            return ""
        return obj.acl_name

    def get_physical_ports(self, obj):
        return PhysicalPort(obj.physical_ports.all(), many=True).data

    def get_device(self, obj):
        return obj.device.id

    def get_port(self, obj):
        return obj.port.id

    def create(self, validated_data):
        """Create a new VirtualPort instance.

        This method takes the validated data and creates a new
        VirtualPort entry in the database.
        """

        # Remove the empty logical_ports_data object that is
        # always received when a new VirtualPort is created
        del validated_data["logical_ports_data"]

        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Update an existing VirtualPort instance.

        This method takes the validated data and updates the
        specific VirtualPort entry.
        """
        updated_instance = super().update(instance, validated_data)

        # LogicalPort associated with this VirtualPort instance is
        # recieved by context. Here each value received is assigned to
        # each parameter of the entry in the database.
        if logical_ports_data := self.context.get("data").get("logical_ports_data"):
            logical_port = models.LogicalPort.objects.get(
                id=int(logical_ports_data.get("id"))
            )

            if logical_ports_data["channel"] == "":
                logical_ports_data["channel"] = None
            logical_port.channel = logical_ports_data.get("channel")

            if logical_port.description != logical_ports_data.get("description"):
                logical_port.description = logical_ports_data.get("description")

            if logical_port.name != logical_ports_data.get("name"):
                logical_port.name = logical_ports_data.get("name")

            if logical_ports_data["trunk"] == "":
                logical_ports_data["trunk"] = None
            logical_port.trunk = logical_ports_data.get("trunk")

            logical_port.save()

        # PhysicalPorts associated with this VirtualPort instance are
        # recieved by context. Here each value received is assigned to
        # each parameter of the entry in the database.
        if physical_ports_data := self.context.get("data").get("physical_ports_data"):
            for physical_port in physical_ports_data:
                if physical_port:
                    physical_port_instance = models.PhysicalPort.objects.get(
                        id=int(physical_port.get("id"))
                    )

                    if physical_port_instance.name != physical_port.get("name"):
                        physical_port_instance.name = physical_port.get("name")

                    if physical_port_instance.size != physical_port.get("size"):
                        physical_port_instance.size = physical_port.get("size")

                    if physical_port_instance.logical_port.id != int(
                        physical_port.get("logical_port")
                    ):
                        physical_port_instance.logical_port = LogicalPort.objects.get(
                            id=int(physical_port.get("logical_port"))
                        )

                    if physical_port_instance.description != physical_port.get(
                        "description"
                    ):
                        physical_port_instance.description = physical_port.get(
                            "description"
                        )

                    physical_port_instance.save()

        return updated_instance

    def to_representation(self, instance):
        """Customize the representation of the VirtualPort instance.

        This method customizes the output format of the serialized data,
        adding more details to the representation if needed.
        """
        representation = super().to_representation(instance)

        # Add LogicalPort details to the VirtualPort representation.
        logical_port_instance = models.LogicalPort.objects.get(
            id=representation["logical_port"]
        )
        representation["logical_port"] = LogicalPort(logical_port_instance).data

        # normalize the vlan id
        representation["vlan_id"] = instance.normalized_vlan_id

        return representation


class VirtualPortMacAddresses(serializers.Serializer):
    macaddr_set = serializers.ListField(
        child=serializers.CharField(allow_null=True, allow_blank=True),
        required=True,
    )
    virtual_port = serializers.PrimaryKeyRelatedField(
        queryset=models.VirtualPort.objects.all(),
    )

    class Meta:
        fields = ["macaddr_set", "virtual_port"]

    def validate_macaddr_set(self, macaddr_set: list[str]):
        if not macaddr_set:
            return []

        # remove none / empty mac addresses
        macaddr_set = [macaddr for macaddr in macaddr_set if macaddr]

        # remove dupes
        macaddr_set = list(set(macaddr_set))
        validate_mac_addresses(macaddr_set)

        return macaddr_set


@register
class SetMacAddressBatch(serializers.Serializer):
    data = VirtualPortMacAddresses(many=True)

    ref_tag = "batch_set_macaddr"

    def save(self):
        for row in self.validated_data.get("data", []):
            virtual_port = row["virtual_port"]
            macaddr_set = row["macaddr_set"]
            virtual_port.port.port_info.macaddr_set = macaddr_set
            virtual_port.port.port_info.save()


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


@register
class DeletePorts(serializers.Serializer):
    virtual = serializers.ListField(child=serializers.IntegerField())
    physical = serializers.ListField(child=serializers.IntegerField())
    logical = serializers.ListField(child=serializers.IntegerField())

    ref_tag = "delete_ports"

    class Meta:
        fields = ["virtual", "physical", "logical"]

    def validate_virtual(self, virtual):
        # load the virtual port instances and check that they belong
        # to the context["org"] org
        virtual_ports = models.VirtualPort.objects.filter(
            id__in=virtual, logical_port__instance__org=self.context["org"]
        )
        return [vp.id for vp in virtual_ports]

    def validate_physical(self, physical):
        # load the physical port instances and check that they belong
        # to the context["org"] org
        physical_ports = models.PhysicalPort.objects.filter(
            id__in=physical, device__instance__org=self.context["org"]
        )
        return [pp.id for pp in physical_ports]

    def validate_logical(self, logical):
        # load the logical port instances and check that they belong
        # to the context["org"] org
        logical_ports = models.LogicalPort.objects.filter(
            id__in=logical, instance__org=self.context["org"]
        )
        return [lp.id for lp in logical_ports]

    def save(self):
        # delete the ports
        if self.validated_data["logical"]:
            models.LogicalPort.objects.filter(
                id__in=self.validated_data["logical"]
            ).delete()

        if self.validated_data["physical"]:
            models.PhysicalPort.objects.filter(
                id__in=self.validated_data["physical"]
            ).delete()

        if self.validated_data["virtual"]:
            models.VirtualPort.objects.filter(
                id__in=self.validated_data["virtual"]
            ).delete()


@register
class Metric(ModelSerializer):
    """Serializer for Metric model."""

    class Meta:
        """Meta class for Metric serializer."""

        model = models.DeviceMetric
        fields = [
            "id",
            "instance",
            "device",
            "data",
            "timestamp",
        ]

    def to_representation(self, instance):
        """Flat json to easy display in datatables."""

        representation = super().to_representation(instance)

        if self.context.get("flatten", True):
            unflat_data = representation.get("data")
            flat_data = flatten(unflat_data, ".")
            return flat_data

        # if self.context.get("keyvalue", True):
        #     unflat_data = representation.get("data")
        #     flat_data = flatten(unflat_data, ".")
        #     kv = [
        #         {"device": instance.device.name, "resource": x, "value": y}
        #         for x, y in flat_data.items()
        #     ]
        #     return kv

    def save(self):
        instance = super().save()
        self.save_physical_port_stats(instance)
        return instance

    def save_physical_port_stats(self, instance):
        for physical_port in instance.device.physical_ports.all():
            try:
                physical_port_stats = models.PhysicalPortStats.objects.get(
                    physical_port=physical_port
                )
            except models.PhysicalPortStats.DoesNotExist:
                physical_port_stats = models.PhysicalPortStats(
                    physical_port=physical_port
                )

            data = physical_port_stats.data
            data["device_metrics"] = PhysicalPort(physical_port).data
            physical_port_stats.data = data
            physical_port_stats.save()


@register
class Vlan(ModelSerializer):
    ref_tag = "vlan"

    facility_name = serializers.SerializerMethodField()
    facility_slug = serializers.SerializerMethodField()

    v4_secondaries = serializers.ListField(
        child=InetAddressSerializerField(), required=False
    )
    v6_secondaries = serializers.ListField(
        child=InetAddressSerializerField(), required=False
    )

    class Meta:
        model = models.Vlan
        fields = "__all__"

    def get_facility_name(self, obj):
        return obj.facility.name if obj.facility else None

    def get_facility_slug(self, obj):
        return obj.facility.slug if obj.facility else None
