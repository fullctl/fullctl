import structlog
from django.utils.translation import gettext_lazy as _
from fullctl.django.models import Organization
from fullctl.django.rest.decorators import serializer_registry
from rest_framework import serializers

from django_devicectl.models import Device

logger = structlog.getLogger("django_structlog")

Serializers, register = serializer_registry()


def validate_positive_integer(value) -> int:
    if value < 0:
        raise serializers.ValidationError(_("This field must be a positive integer."))
    return value


@register
class MRTGData(serializers.Serializer):
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


@register
class MRTGSwitchToSwitch(serializers.Serializer):
    ref_tag = "mrtg_switch_to_switch"

    side_a_name = serializers.CharField()
    side_b_name = serializers.CharField()
    bps_out = serializers.FloatField()
    timestamp = serializers.IntegerField(validators=[validate_positive_integer])

    class Meta:
        fields = ["side_a_name", "side_b_name", "bps_out", "timestamp"]

    def validate(self, validated_data: dict) -> dict:
        org = self.context["org"]
        
        # assert that side-a != side-b
        if validated_data["side_a_name"] == validated_data["side_b_name"]:
            raise serializers.ValidationError(
                _("side_a_name and side_b_name must be different")
            )

        # assert that both devices exist
        side_a_exists = Device.objects.filter(
            name=validated_data["side_a_name"], instance__org_id=org.id
        ).exists()

        side_b_exists = Device.objects.filter(
            name=validated_data["side_b_name"], instance__org_id=org.id
        ).exists()

        if not side_a_exists:
            raise serializers.ValidationError(
                _("Device with name {side_a_name} does not exist").format(
                    **validated_data
                )
            )

        if not side_b_exists:
            raise serializers.ValidationError(
                _("Device with name {side_b_name} does not exist").format(
                    **validated_data
                )
            )

        return validated_data


class MRTGSwitchToSwitchMany(serializers.Serializer):
    """
    Describes a list of MRTGSwitchToSwitch data points
    """

    data = serializers.ListField(child=MRTGSwitchToSwitch())

    class Meta:
        fields = ["data"]
