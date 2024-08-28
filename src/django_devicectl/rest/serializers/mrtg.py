import structlog

from django.utils.translation import gettext_lazy as _
from fullctl.django.rest.decorators import serializer_registry
from rest_framework import serializers

logger = structlog.getLogger("django_structlog")

Serializers, register = serializer_registry()

def validate_positive_integer(value) -> int:
    if value < 0:
        raise serializers.ValidationError(_("This field must be a positive integer."))
    return value

@register
class SflowData(serializers.Serializer):
    """
    Describes a single sflow data point for the purpose of writing to the
    database
    """

    ref_tag = "mrtg"

    org = serializers.CharField()
    org_id = serializers.IntegerField(validators=[validate_positive_integer])
    ix_id = serializers.IntegerField(validators=[validate_positive_integer])
    port_id = serializers.IntegerField(validators=[validate_positive_integer])
    device_id = serializers.IntegerField(validators=[validate_positive_integer])
    timestamp = serializers.IntegerField(validators=[validate_positive_integer])
    bps_in = serializers.FloatField()
    bps_out = serializers.FloatField()
    bps_in_max = serializers.FloatField()
    bps_out_max = serializers.FloatField()