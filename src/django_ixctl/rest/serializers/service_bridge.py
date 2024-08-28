from fullctl.django.rest.decorators import serializer_registry
from fullctl.django.rest.serializers import ModelSerializer
from rest_framework import serializers

import django_ixctl.models.ixctl as models

Serializers, register = serializer_registry()


@register
class Prefix(ModelSerializer):
    class Meta:
        model = models.InternetExchangePrefix
        fields = ["id", "ix", "prefix"]


@register
class InternetExchange(ModelSerializer):
    org_id = serializers.SerializerMethodField()
    org_slug = serializers.SerializerMethodField()

    class Meta:
        model = models.InternetExchange
        fields = [
            "org_id",
            "org_slug",
            "id",
            "slug",
            "pdb_id",
            "name",
            "slug",
            "verified",
            "mtu",
            "vlan_id",
            "graph_traffic_source",
        ]

    def get_org_id(self, ix):
        return ix.instance.org.permission_id


    def get_org_slug(self, ix):
        return ix.instance.org.slug

@register
class InternetExchangeMember(ModelSerializer):
    ix = serializers.SerializerMethodField()
    ix_name = serializers.SerializerMethodField()
    pdb_ix_id = serializers.SerializerMethodField()
    org_id = serializers.SerializerMethodField()

    macaddr_set = serializers.ListSerializer(
        child=serializers.CharField(),
        read_only=True,
    )

    class Meta:
        model = models.InternetExchangeMember
        fields = [
            "id",
            "ix_id",
            "org_id",
            "pdb_ix_id",
            "ix",
            "ix_name",
            "name",
            "speed",
            "asn",
            "ipaddr4",
            "ipaddr6",
            "is_rs_peer",
            "macaddr",
            "macaddr_set",
            "md5",
            "port",
        ]

    def get_ix(self, member):
        if "ix" in self.context.get("joins", []):
            return InternetExchange(instance=member.ix).data
        return None

    def get_ix_name(self, member):
        return member.ix.name

    def get_pdb_ix_id(self, member):
        return member.ix.pdb_id

    def get_org_id(self, member):
        return member.ix.instance.org.permission_id

@register
class Routeserver(ModelSerializer):
    ix = serializers.SerializerMethodField()
    pdb_ix_id = serializers.SerializerMethodField()

    class Meta:
        model = models.Routeserver
        fields = [
            "id",
            "ix_id",
            "pdb_ix_id",
            "ix",
            "name",
            "asn",
            "router_id",
        ]

    def get_ix(self, member):
        if "ix" in self.context.get("joins", []):
            return InternetExchange(instance=member.ix).data
        return None

    def get_pdb_ix_id(self, member):
        return member.ix.pdb_id
