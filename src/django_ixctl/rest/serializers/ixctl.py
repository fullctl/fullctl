try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

import fullctl.service_bridge.devicectl as devicectl
import fullctl.service_bridge.pdbctl as pdbctl
import fullctl.service_bridge.prefixctl as prefixctl
import yaml
from django.conf import settings
from django.core.validators import RegexValidator
from django.utils.translation import gettext_lazy as _
from django_inet.rest import IPAddressField
from fullctl.django.models.concrete.tasks import TaskLimitError
from fullctl.django.rest.decorators import serializer_registry
from fullctl.django.rest.serializers import (
    ModelSerializer,
    RequireContext,
    SoftRequiredValidator,
)
from fullctl.django.inet.validators import validate_mac_address, validate_mac_addresses
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.validators import UniqueTogetherValidator

import django_ixctl.enum
import django_ixctl.models as models
from django_ixctl.peeringdb import import_exchange, import_org

import structlog
logger = structlog.getLogger('django_structlog')

Serializers, register = serializer_registry()


@register
class ImportOrganization(RequireContext, serializers.Serializer):
    pdb_org_id = serializers.IntegerField(required=False)

    required_context = ["instance"]

    ref_tag = "imporg"

    class Meta:
        fields = [
            "pdb_org_id",
        ]

    def validate_pdb_org_id(self, value):
        if not value:
            return 0
        self.pdb_org = pdbctl.Organization().object(value)
        if not self.pdb_org:
            raise ValidationError(_("Unknown peeringdb organization"))
        return self.pdb_org.id

    def save(self):
        instance = self.context.get("instance")
        pdb_org = getattr(self, "pdb_org", None)
        return import_org(pdb_org, instance)


@register
class ImportExchange(RequireContext, serializers.Serializer):
    pdb_ix_id = serializers.IntegerField()

    required_context = ["instance"]

    ref_tag = "impix"

    class Meta:
        fields = [
            "pdb_ix_id",
        ]

    def validate_pdb_ix_id(self, value):
        instance = self.context.get("instance")
        if not value:
            return 0

        try:
            self.pdb_ix = pdbctl.InternetExchange().object(value)
        except KeyError:
            raise ValidationError(_("Unknown peeringdb exchange"))

        qset = models.InternetExchange.objects.filter(
            instance=instance, pdb_id=self.pdb_ix.id
        )

        if qset.exists():
            raise ValidationError(_("You have already imported this exchange"))

        return self.pdb_ix.id

    def validate(self, cleaned_data):
        instance = self.context.get("instance")
        slug = models.InternetExchange.default_slug(self.pdb_ix.name)
        qset = models.InternetExchange.objects.filter(instance=instance, slug=slug)
        if qset.exists():
            raise ValidationError(
                _("You already have an exchange with the identifier `{}`").format(slug)
            )
        return cleaned_data

    def save(self):
        instance = self.context.get("instance")
        ix = import_exchange(self.pdb_ix, instance)
        return ix


@register
class PermissionRequest(ModelSerializer):
    class Meta:
        model = models.PermissionRequest
        fields = ["user", "type", "org"]


@register
class Prefix(ModelSerializer):
    class Meta:
        model = models.InternetExchangePrefix
        fields = ["id", "ix", "prefix"]


@register
class UpdateLAN(ModelSerializer):
    ref_tag = "update_lan"

    class Meta:
        model = models.InternetExchange
        fields = [
            "id",
            "vlan_id",
            "mtu",
        ]


@register
class InternetExchange(ModelSerializer):

    graph_traffic_source = serializers.CharField(read_only=True)

    class Meta:
        model = models.InternetExchange
        fields = [
            "pdb_id",
            "urlkey",
            "instance",
            "ixf_export_privacy",
            "name",
            "slug",
            "source_of_truth",
            "verified",
            "mtu",
            "vlan_id",
            "notes",
            "public_view",
            "graph_traffic_source",
        ]
        extra_kwargs = {
            "slug": {
                "required": False,
                "allow_blank": True,
                "allow_null": True,
                "default": None,
            }
        }

        read_only_fields = [
            "verified",
            "source_of_truth",
        ]

    def validate(self, cleaned_data):
        instance = cleaned_data.get("instance")
        slug = cleaned_data.get("slug")
        if not slug:
            slug = models.InternetExchange.default_slug(cleaned_data["name"])
        qset = models.InternetExchange.objects.filter(instance=instance, slug=slug)

        if self.instance and self.instance.id:
            qset = qset.exclude(id=self.instance.id)

        if qset.exists():
            raise ValidationError(
                _("You already have an exchange with the identifier `{}`").format(slug)
            )
        cleaned_data["slug"] = slug
        return cleaned_data


@register
class InternetExchangeMember(ModelSerializer):
    ipaddr4 = IPAddressField(
        version=4,
        allow_blank=True,
        allow_null=True,
        required=False,
        default=None,
    )
    ipaddr6 = IPAddressField(
        version=6,
        allow_blank=True,
        allow_null=True,
        required=False,
        default=None,
    )

    macaddr = serializers.CharField(
        allow_blank=True,
        allow_null=True,
        required=False,
        default=None,
    )

    macaddr_set = serializers.ListSerializer(
        child=serializers.CharField(),
        required=False,
    )

    macaddr_warnings = serializers.SerializerMethodField()

    display_name = serializers.CharField(read_only=True)
    prefix_set_name = serializers.SerializerMethodField()
    port_name = serializers.SerializerMethodField()

    status = serializers.ChoiceField(
        choices=django_ixctl.enum.PORT_STATE,
        allow_blank=True,
        allow_null=True,
        required=False,
        default="ok",
    )

    # conditional field#
    if settings.MEMBER_CASE_NUMBERS_ENABLED:
        case_number = serializers.CharField(
            allow_blank=False,
            allow_null=False,
            required=True,
            write_only=True,
        )

    class Meta:
        model = models.InternetExchangeMember
        fields = [
            "id",
            "pdb_id",
            "ix",
            "ixf_member_type",
            "ixf_state",
            "asn",
            "name",
            "display_name",
            "ipaddr4",
            "ipaddr6",
            "macaddr",
            "macaddr_set",
            "macaddr_warnings",
            "as_macro",
            "as_macro_override",
            "as_macro_negate",
            "is_rs_peer",
            "status",
            "speed",
            "md5",
            "prefix4",
            "prefix6",
            "prefix_set",
            "prefix_set_name",
            "port",
            "port_name",
            "meta",
        ]


        if settings.MEMBER_CASE_NUMBERS_ENABLED:
            fields.append("case_number")

        validators = [
            SoftRequiredValidator(
                fields=("ipaddr4", "ipaddr6"),
                message=_("Input required for IPv4 or IPv6"),
            ),
            UniqueTogetherValidator(
                queryset=models.InternetExchangeMember.objects.all(),
                fields=("ipaddr4", "ix"),
                message="IPv4 address exists already in this exchange",
            ),
            UniqueTogetherValidator(
                queryset=models.InternetExchangeMember.objects.all(),
                fields=("ipaddr6", "ix"),
                message="IPv6 address exists already in this exchange",
            ),
        ]

    @property
    def prefix_sets_by_slug(self) -> dict[str, prefixctl.PrefixSet]:
        """
        Returns prefix sets cached by slugs for all members being
        serialized. If the cache does not exist, it will be created.
        """
        if hasattr(self, "_prefix_sets_by_slug"):
            return self._prefix_sets_by_slug

        # we need an org instance to get the prefix sets
        org_instance = self.context.get("instance")
        if org_instance:
            org_slug = org_instance.org.slug
        else:
            org_slug = None

        prefix_sets = prefixctl.PrefixSet().objects(org=org_slug)
        self._prefix_sets_by_slug = {prefixset.slug: prefixset for prefixset in prefix_sets}
        return self._prefix_sets_by_slug

    @property
    def macaddresses(self) -> dict[str, models.MacAddress]:
        """
        Returns mac addresses cached.
        If the cache does not exist, it will be created.
        """
        if hasattr(self, "_macaddresses"):
            return self._macaddresses

        # get the ix instance
        # self.instance may be a single instance or a queryset

        if isinstance(self.instance, models.InternetExchangeMember):
            ix = self.instance.ix
        else:
            ix = self.instance[0].ix

        macaddresses = models.MacAddress.objects.filter(member__ix=ix).select_related("member")

        self._macaddresses = {
            "by_mac": {},
            "by_member": {},
        }

        for mac in macaddresses:
            self._macaddresses["by_mac"].setdefault(str(mac.address), []).append(mac.member)
            self._macaddresses["by_member"].setdefault(mac.member.id, []).append(str(mac.address))

        return self._macaddresses

    @property
    def ports(self) -> dict[str, devicectl.Port]:
        """
        Returns ports cached.
        If the cache does not exist, it will be created.
        """
        if hasattr(self, "_ports"):
            return self._ports

        instance = self.context.get("instance")
        if instance:
            org_id = instance.org.id
        else:
            org_id = None

        ports = devicectl.Port().objects(org_id=org_id)

        self._ports = {port.id: port for port in list(ports)}
        return self._ports


    def validate_ipaddr4(self, ipaddr4):
        if not ipaddr4:
            return None
        return ipaddr4

    def validate_ipaddr6(self, ipaddr6):
        if not ipaddr6:
            return None
        return ipaddr6

    def validate_macaddr(self, macaddr: str):
        if not macaddr:
            return None

        validate_mac_address(macaddr)

        return macaddr

    def validate_macaddr_set(self, macaddr_set: list[str]):
        if not macaddr_set:
            return []
        
        # check for duplicates within the passed list
        if len(macaddr_set) != len(set(macaddr_set)):
            raise ValidationError("Duplicate mac addresses found")

        validate_mac_addresses(macaddr_set)

        return macaddr_set

    def validate_md5(self, md5):
        if not md5:
            return None
        return md5

    def validate_prefix_set(self, prefix_set_slug: str):
        if not prefix_set_slug:
            return None

        # validate format
        try:
            source, slug = prefix_set_slug.split("::")

            if source != "prefixctl":
                raise ValidationError(_("Invalid prefix set source: {source}. Source should be `prefixctl`").format(source=source))

        except ValueError:
            raise ValidationError(_("Invalid prefix set slug. Format should be `prefixctl::<slug>`"))

        prefix_set = self.prefix_sets_by_slug.get(slug)

        if not prefix_set:
            raise ValidationError(_("Prefix set `{prefix_set_slug}` not found").format(prefix_set_slug=prefix_set_slug))

        return prefix_set_slug

    def validate_port(self, port):
        """
        Validates the port to make sure it exists and belongs to the requesting
        organization
        """
        org_instance = self.context.get("instance")

        if not port:
            return port

        # check that port exists and belongs to the requesting organization

        port_object = devicectl.Port().first(
            id=int(port), org_slug=org_instance.org.slug
        )

        if not port_object:
            raise ValidationError(_("Port not found"))

        return port_object.id

    def validate(self, data:dict) -> dict:

        # if case numbers are enabled push them into meta under
        # a case_number key (list)

        if settings.MEMBER_CASE_NUMBERS_ENABLED:
            case_number = data.get("case_number")
            meta = data.get("meta", {})
            if case_number:
                meta.setdefault("case_number", []).append(case_number)
                data["meta"] = meta
            data.pop("case_number", None)

        return data

    def to_representation(self, instance: models.InternetExchangeMember) -> dict:
        """
        Override to_representation to remove meta.case_number if
        settings.MEMBER_CASE_NUMBERS_ENABLED is False
        """
        data = super().to_representation(instance)
        if not settings.MEMBER_CASE_NUMBERS_ENABLED:
            if data.get("meta") and "case_number" in data.get("meta"):
                del data.meta["case_number"]
        return data


    def get_prefix_set_name(self, obj):
        if not obj.prefix_set:
            return None

        prefix_set = self.prefix_sets_by_slug.get(obj.prefix_set_slug)

        if not prefix_set:
            return None

        return prefix_set.name

    def save(self):
        member = super().save()
        # member needs to be saved before we can set the macaddr_set
        member.macaddr_set = self.validated_data.get("macaddr_set", [])

        return member

    def get_port_name(self, member):
        if not member.port:
            return None
        try:
            port = self.ports.get(member.port.id)
            return port.virtual_port_name
        except AttributeError:
            return None

    def get_macaddr_warnings(self, obj):
        """
        Checks if macaddr_set contains any mac addresses
        that exist on another member
        """

        # collect member's mac addresses from self.macaddresses
        macaddr_set = self.macaddresses["by_member"].get(obj.id, [])

        if not macaddr_set:
            return []

        warnings = []

        for macaddr in macaddr_set:
            warnings.extend([f"MAC address {macaddr} also exists on AS{member.asn} - {member.ipaddr4}" for member in self.macaddresses["by_mac"].get(macaddr,[]) if member.id != obj.id])

        return warnings


        

@register
class InternetExchangeMemberDetail(InternetExchangeMember):
    ref_tag = "member_detail"
    port = serializers.SerializerMethodField()
    prefix_set_name = serializers.SerializerMethodField()

    class Meta(InternetExchangeMember.Meta):
        fields = InternetExchangeMember.Meta.fields + ["port", "prefix_set_name"]

    def get_port(self, member):
        if not member.port:
            return None
        try:
            port = member.port.object.__dict__
            port["device"] = port["device"].__dict__
            return port
        except AttributeError:
            return None


@register
class Routeserver(ModelSerializer):
    router_id = IPAddressField(
        version=4,
    )
    operational_status = serializers.CharField(read_only=True)

    class Meta:
        model = models.Routeserver
        fields = [
            "id",
            "ix",
            "name",
            "display_name",
            "asn",
            "router_id",
            "operational_status",
            "ars_type",
            "max_as_path_length",
            "no_export_action",
            "rpki_bgp_origin_validation",
            "graceful_shutdown",
            "extra_config",
            "routeserver_config_status",
            "routeserver_config_generated_time",
            "routeserver_config_response",
            "routeserver_config_error",
        ]

    def validate_extra_config(self, value):
        try:
            data = yaml.load(value, Loader=Loader)
        except Exception as exc:
            raise serializers.ValidationError(f"Invalid yaml formatting: {exc}")

        if data and not isinstance(data, dict):
            raise serializers.ValidationError("Config object literal expected")
        return value

    def save(self):
        r = super().save()
        try:
            r.routeserver_config.queue_generate()
        except TaskLimitError:
            pass
        return r


@register
class RouteserverConfig(ModelSerializer):
    class Meta:
        model = models.RouteserverConfig
        fields = [
            "routeserver",
            "generated",
            "body",
        ]


@register
class DefaultExchange(ModelSerializer):
    ref_tag = "default_ix"

    class Meta:
        model = models.OrganizationDefaultExchange
        fields = ["org", "ix"]

    def save(self):
        org = self.validated_data["org"]
        ix = self.validated_data["ix"]

        models.InternetExchange.set_default_exchange_for_org(org, ix)


@register
class PeeringDBRouteserver(serializers.Serializer):
    ref_tag = "pdbrouteserver"

    id = serializers.IntegerField()
    router_id = serializers.SerializerMethodField()
    name = serializers.CharField(read_only=True)
    asn = serializers.IntegerField(read_only=True)

    class Meta:
        fields = ["id", "router_id", "name", "asn"]

    def get_router_id(self, obj):
        return obj.ipaddr4 or ""


@register
class Network(ModelSerializer):
    class Meta:
        model = models.Network
        fields = ["pdb_id", "asn", "name", "display_name"]


@register
class NetworkPresence(InternetExchangeMember):
    org = serializers.SerializerMethodField()
    org_name = serializers.SerializerMethodField()
    access = serializers.SerializerMethodField()
    ref_tag = "presence"

    class Meta(InternetExchangeMember.Meta):
        fields = InternetExchangeMember.Meta.fields + [
            "org",
            "org_name",
            "ix_name",
            "access",
        ]

    @property
    def permrequest(self):
        user = self.context.get("user")
        if not hasattr(self, "_permrequest"):
            self._permrequest = {
                pr.org_id: True
                for pr in models.PermissionRequest.objects.filter(user=user)
            }
        return self._permrequest

    def get_org(self, obj):
        return obj.org.slug

    def get_org_name(self, obj):
        return obj.org.name

    def get_access(self, obj):
        perms = self.context.get("perms")
        if not perms:
            return False

        namespace = self.get_grainy(obj)

        access_u = perms.check(f"{namespace}.?", "u")
        access_r = perms.check(f"{namespace}", "r")

        if access_u:
            return "manage"

        if access_r:
            return "view"

        if self.get_access_pending(obj):
            return "pending"

        return "denied"

    def get_access_pending(self, obj):
        return self.permrequest.get(obj.org.id, False)


class OperationalStatusSerializer(serializers.Serializer):
    operational_status = serializers.CharField()

    class Meta:
        fields = ["operational_status"]


@register
class BGPState(serializers.Serializer):
    up = serializers.CharField()
    last_change = serializers.CharField()
    state = serializers.CharField()
    protocol = serializers.CharField()
    name = serializers.CharField()
    asn = serializers.CharField()
    address = serializers.CharField()
    routeserver_router_id = serializers.CharField()
    routeserver_hostname = serializers.CharField()
    router_id = serializers.CharField(required=False, default=None)
    routes_imported = serializers.IntegerField(required=False, default=0)
    routes_exported = serializers.IntegerField(required=False, default=0)
    import_updates_received = serializers.IntegerField(required=False, default=0)
    import_updates_rejected = serializers.IntegerField(required=False, default=0)
    import_updates_filtered = serializers.IntegerField(required=False, default=0)
    import_updates_ignored = serializers.IntegerField(required=False, default=0)
    import_updates_accepted = serializers.IntegerField(required=False, default=0)
    import_withdraws_received = serializers.IntegerField(required=False, default=0)
    import_withdraws_rejected = serializers.IntegerField(required=False, default=0)
    import_withdraws_ignored = serializers.IntegerField(required=False, default=0)
    import_withdraws_accepted = serializers.IntegerField(required=False, default=0)
    export_updates_received = serializers.IntegerField(required=False, default=0)
    export_updates_rejected = serializers.IntegerField(required=False, default=0)
    export_updates_filtered = serializers.IntegerField(required=False, default=0)
    export_updates_accepted = serializers.IntegerField(required=False, default=0)
    export_withdraws_received = serializers.IntegerField(required=False, default=0)
    export_withdraws_accepted = serializers.IntegerField(required=False, default=0)

    ref_tag = "bgp_state"

    class Meta:
        fields = "__all__"
