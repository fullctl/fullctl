from fullctl.django.rest.decorators import serializer_registry
from fullctl.django.rest.serializers import ModelSerializer
from rest_framework import serializers

import django_peerctl.models.peerctl as models

Serializers, register = serializer_registry()


@register
class Network(ModelSerializer):
    class Meta:
        model = models.Network
        fields = ["id", "name", "asn", "as_set", "prefix4", "prefix6"]


@register
class RequestDevicectlSync(serializers.Serializer):
    org_id = serializers.IntegerField()
    ref_tag = "request_devicectl_sync"

    class Meta:
        fields = ["org_id"]


@register
class PortInfo(serializers.ModelSerializer):
    ref_tag = "port_info"

    # we cannot pass ref_id as ref_id because ref_id
    # is a core property of the service bridge client data object
    # instead alias it to source_ref_id
    source_ref_id = serializers.CharField(source="ref_id")

    class Meta:
        model = models.PortInfo
        fields = [
            "id",
            "net",
            "port",
            "source_ref_id",
            "status",
            "is_route_server_peer",
            "ip_address_4",
            "ip_address_6",
            "traffic_threshold_alert",
        ]