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

    macaddr_warnings = serializers.SerializerMethodField()

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
            "macaddr_warnings",
            "md5",
            "port",
        ]

    @property
    def macaddresses(self) -> dict[str, models.MacAddress]:
        """
        Returns mac addresses cached.
        If the cache does not exist, it will be created.
        """
        if hasattr(self, "_macaddresses"):
            return self._macaddresses

        if isinstance(self.instance, models.InternetExchangeMember):
            members = [self.instance]
        else:
            members = self.instance

        exchanges = set([member.ix for member in members])
        macaddresses = models.MacAddress.objects.filter(member__ix__in=exchanges).select_related("member")

        self._macaddresses = {
            "by_mac": {},
            "by_member": {},
        }

        for mac in macaddresses:
            ix_id = mac.member.ix_id
            self._macaddresses["by_mac"].setdefault(ix_id, {}).setdefault(str(mac.address), []).append(mac.member)
            self._macaddresses["by_member"].setdefault(ix_id, {}).setdefault(mac.member.id, []).append(str(mac.address))

        print(self._macaddresses)

        return self._macaddresses

    def get_macaddr_warnings(self, obj):
        """
        Checks if macaddr_set contains any mac addresses
        that exist on another member
        """

        # collect member's mac addresses from self.macaddresses
        macaddr_set = self.macaddresses["by_member"].get(obj.ix_id, {}).get(obj.id, [])

        if not macaddr_set:
            return []

        warnings = []

        for macaddr in macaddr_set:
            warnings.extend(
                [
                    f"MAC address {macaddr} also exists on AS{member.asn} - {member.ipaddr4}" 
                    for member in self.macaddresses["by_mac"].get(obj.ix_id, {}).get(macaddr,[]) 
                    if member.id != obj.id
                ]
            )

        return warnings

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
            "event",
        ]

    def get_ix(self, member):
        if "ix" in self.context.get("joins", []):
            return InternetExchange(instance=member.ix).data
        return None

    def get_pdb_ix_id(self, member):
        return member.ix.pdb_id


@register
class RouteserverMember(ModelSerializer):
    ref_tag = "routeserver_member"

    class Meta:
        model = models.RouteserverMember
        fields = "__all__"
