import django_peeringdb.models.concrete as models
from django.utils.translation import ugettext_lazy as _
from django_inet.rest import IPAddressField
from fullctl.django.rest.decorators import serializer_registry
from fullctl.django.rest.serializers import ModelSerializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

Serializers, register = serializer_registry()


@register
class Network(ModelSerializer):
    class Meta:
        model = models.Network
        fields = [
            "id",
            "org_id",
            "asn",
            "name",
            "name_long",
            "aka",
            "website",
            "info_type",
            "info_prefixes4",
            "info_prefixes6",
            "info_traffic",
            "info_ratio",
            "info_scope",
            "info_unicast",
            "info_multicast",
            "info_ipv6",
            "irr_as_set",
            "policy_url",
            "policy_general",
            "policy_locations",
            "policy_ratio",
            "policy_contracts",
        ]


@register
class InternetExchange(ModelSerializer):
    class Meta:
        model = models.InternetExchange
        fields = [
            "id",
            "org_id",
            "name",
            "name_long",
            "aka",
            "city",
            "country",
            "region_continent",
            "tech_email",
            "tech_phone",
            "policy_email",
            "policy_phone",
            "service_level",
            "terms",
            "media",
            "url_stats",
            "website",
        ]


@register
class Facility(ModelSerializer):
    class Meta:
        model = models.Facility
        fields = [
            "id",
            "org_id",
            "name",
            "name_long",
            "aka",
            "city",
            "country",
            "address1",
            "address2",
            "floor",
            "suite",
            "longitude",
            "latitude",
            "website",
            "clli",
            "rencode",
            "npanxx",
            "sales_email",
            "sales_phone",
            "tech_email",
            "tech_phone",
            "available_voltage_services",
            "diverse_serving_substations",
            "property",
        ]


@register
class IXLanPrefix(ModelSerializer):
    class Meta:
        model = models.IXLanPrefix
        fields = [
            "id",
            "ixlan_id",
            "prefix",
            "protocol",
        ]


@register
class NetworkContact(ModelSerializer):
    asn = serializers.SerializerMethodField()

    class Meta:
        model = models.NetworkContact
        fields = [
            "id",
            "net_id",
            "role",
            "name",
            "visible",
            "phone",
            "email",
            "asn",
        ]

    def get_asn(self, poc):
        return poc.net.asn


@register
class NetworkIXLan(ModelSerializer):
    net = serializers.SerializerMethodField()
    ix_id = serializers.IntegerField(source="ixlan_id")
    ix = serializers.SerializerMethodField()

    name = serializers.SerializerMethodField()
    as_set = serializers.SerializerMethodField()

    class Meta:
        model = models.NetworkIXLan
        fields = [
            "id",
            "net",
            "net_id",
            "ixlan_id",
            "ix_id",
            "ix",
            "speed",
            "asn",
            "ipaddr4",
            "ipaddr6",
            "is_rs_peer",
            "operational",
            "name",
            "as_set",
        ]

    def get_net(self, netixlan):
        if "net" in self.context.get("joins", []):
            return Network(instance=netixlan.net).data
        return None

    def get_ix(self, netixlan):
        if "ix" in self.context.get("joins", []):
            return InternetExchange(instance=netixlan.ixlan.ix).data
        return None

    def get_name(self, netixlan):
        return netixlan.net.name

    def get_as_set(self, netixlan):
        return netixlan.net.irr_as_set


@register
class NetworkFacility(ModelSerializer):
    class Meta:
        model = models.NetworkFacility
        fields = [
            "id",
            "net_id",
            "fac_id",
        ]


@register
class InternetExchangeFacility(ModelSerializer):
    class Meta:
        model = models.InternetExchangeFacility
        fields = [
            "id",
            "ix_id",
            "fac_id",
        ]
