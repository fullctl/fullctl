import ipaddress

import structlog
from django.utils.translation import gettext_lazy as _
from fullctl.django.rest.decorators import serializer_registry
from rest_framework import serializers

import django_devicectl.sflow as sflow

logger = structlog.getLogger("django_structlog")

Serializers, register = serializer_registry()


def validate_ip_address(value: str) -> str:
    try:
        ipaddress.ip_address(value)
    except ValueError:
        raise serializers.ValidationError(f"Invalid IP address: {value}")
    return value


def validate_positive_integer(value) -> int:
    if value < 0:
        raise serializers.ValidationError(_("This field must be a positive integer."))
    return value


"""
def validate_line_protocol(value:str) -> str:
    Takes an InfluxDB line protocol string with sflow data and validates it
    using the SFlowData serializer

    # we don't actually connect to an InfluxDB instance here, we just use the client
    # to parse the line protocol string
    client: InfluxDBClient = InfluxDBClient()

    try:
        point: Point = client.write_api().parse_line(value)
    except Exception as e:
        raise serializers.ValidationError(f"Invalid InfluxDB line protocol: {value}")

    # assert name is sflow
    if point.measurement != "sflow":
        raise serializers.ValidationError(f"Invalid measurement: {point.measurement}")

    result = {**point.tags, **point.fields}

    serializer = SflowData(data=result)

    serializer.is_valid(raise_exception=True)

    return value
"""


@register
class SflowData(serializers.Serializer):
    """
    Describes a single sflow data point for the purpose of writing to the
    database
    """

    ref_tag = "sflow"

    org = serializers.CharField()
    org_id = serializers.IntegerField(validators=[validate_positive_integer])
    ix_id = serializers.IntegerField(validators=[validate_positive_integer])
    asn_src = serializers.IntegerField(validators=[validate_positive_integer])
    asn_dst = serializers.IntegerField(validators=[validate_positive_integer])
    port_id_src = serializers.IntegerField(validators=[validate_positive_integer])
    port_id_dst = serializers.IntegerField(validators=[validate_positive_integer])
    device_id_src = serializers.IntegerField(validators=[validate_positive_integer])
    device_id_dst = serializers.IntegerField(validators=[validate_positive_integer])
    mac_src = serializers.CharField()
    mac_dst = serializers.CharField()
    bytes = serializers.IntegerField(validators=[validate_positive_integer])
    packets = serializers.IntegerField(validators=[validate_positive_integer])
    timestamp = serializers.IntegerField(validators=[validate_positive_integer])

    def save(self):
        sflow.save([self.validated_data])


@register
class SflowBatch(serializers.Serializer):
    """
    Describes multiple sflow data points for the purpose of writing to the
    database
    """

    ref_tag = "sflow_batch"

    data = serializers.ListField(child=SflowData())

    def save(self):
        sflow.save(self.validated_data["data"])


@register
class ASNTrafficRow(serializers.Serializer):
    """
    Describes a row an the AS traffic table

    ```
    {
      "asn": 1234,
      "name": "AS Name",
      "bps_in_current": 627096726,
      "bps_in_average": 218396553,
      "bps_in_max": 1226340871,
      "bps_out_current": 394605363,
      "bps_out_average": 214994972,
      "bps_out_max": 1286596635
    }
    ```
    """

    ref_tag = "asn_table_row"

    asn = serializers.IntegerField(validators=[validate_positive_integer])
    name = serializers.CharField()
    bps_in_current = serializers.FloatField()
    bps_in_average = serializers.FloatField()
    bps_in_max = serializers.FloatField()
    bps_out_current = serializers.FloatField()
    bps_out_average = serializers.FloatField()
    bps_out_max = serializers.FloatField()
