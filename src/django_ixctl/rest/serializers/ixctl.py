try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

import fullctl.service_bridge.aaactl as aaactl
import fullctl.service_bridge.devicectl as devicectl
import fullctl.service_bridge.pdbctl as pdbctl
import fullctl.service_bridge.prefixctl as prefixctl
import structlog
import yaml
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django_inet.rest import IPAddressField
from fullctl.django.inet.validators import validate_mac_address, validate_mac_addresses
from fullctl.django.models.concrete.tasks import Task, TaskLimitError
from fullctl.django.rest.decorators import serializer_registry
from fullctl.django.rest.serializers import (
    ModelSerializer,
    RequireContext,
    SoftRequiredValidator,
)
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.validators import UniqueTogetherValidator

import django_ixctl.enum
import django_ixctl.models as models
import django_ixctl.port_automation as port_automation
from django_ixctl.peeringdb import import_exchange, import_org

logger = structlog.getLogger("django_structlog")

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
    email_alert_recipients = serializers.ListField(
        child=serializers.EmailField(),
        required=False,
        allow_null=True,
        default=None,
    )

    ixf_id = serializers.IntegerField(required=False)

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
            "learned_mac_addresses",
            "limit_mac_addresses",
            "traffic_poll_time",
            "email_alert_recipients",
            "ixf_id",
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

    def save_email_alert_recipients(self, recipients: list[str]):
        org = self.context.get("org")
        aaactl.PointOfContact().save_poc(
            delivery_type="email",
            recipients=recipients,
            org_slug=org.slug,
            org_id=org.id,
            poc_type="notifications",
            service="ixctl",
        )

    def save(self, **kwargs):
        email_alert_recipients = self.validated_data.pop("email_alert_recipients")
        ixf_id = self.validated_data.pop("ixf_id", None)

        instance = super().save(**kwargs)
        self.save_email_alert_recipients(recipients=email_alert_recipients)

        instance.ixf_id = ixf_id
        instance.save()

        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation["email_alert_recipients"] = self.get_email_alert_recipients()
        return representation

    def get_email_alert_recipients(self) -> list[str]:
        org = self.context.get("org")
        return aaactl.PointOfContact().get_email_alert_recipients(
            org=org, service="ixctl"
        )


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

    # defaults to 1 if not set, but will be ignored if
    # parent ix is not limiting mac addresses
    macaddr_limit = serializers.IntegerField(
        allow_null=True,
        required=False,
        default=1,
    )

    display_name = serializers.CharField(read_only=True)
    prefix_set_name = serializers.SerializerMethodField()

    port_name = serializers.SerializerMethodField()

    port_set = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        write_only=True,
        help_text=_(
            "List of physical ports to be used for the port configuration intent"
        ),
    )

    port_config_intent = serializers.ChoiceField(
        required=False,
        default=None,
        allow_null=True,
        write_only=True,
        choices=django_ixctl.enum.PORT_CONFIG_INTENT,
        help_text=_(
            "Name of the port configuration intent to apply to the port. This needs to be set if you intend to make changes to lag, quantity, or size. Otherwise changes to those fields will raise a validation error."
        ),
    )

    status = serializers.ChoiceField(
        choices=django_ixctl.enum.PORT_STATE,
        allow_blank=True,
        allow_null=True,
        required=False,
        default="ok",
    )

    # conditional field#
    if settings.MEMBER_CASE_NUMBERS_ENABLED:
        ALLOW_BLANK = True
        case_number = serializers.CharField(
            allow_blank=ALLOW_BLANK,
            allow_null=ALLOW_BLANK,
            required=not ALLOW_BLANK,
            write_only=True,
        )
        work_order = serializers.CharField(
            allow_blank=ALLOW_BLANK,
            allow_null=ALLOW_BLANK,
            required=not ALLOW_BLANK,
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
            "macaddr_limit",
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
            "port_config_intent",
            "port_name",
            "port_size",
            "port_quantity",
            "port_set",
            "lag",
            "meta",
        ]

        if settings.MEMBER_CASE_NUMBERS_ENABLED:
            fields.append("case_number")
            fields.append("work_order")

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
        self._prefix_sets_by_slug = {
            prefixset.slug: prefixset for prefixset in prefix_sets
        }
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

        macaddresses = models.MacAddress.objects.filter(member__ix=ix).select_related(
            "member"
        )

        self._macaddresses = {
            "by_mac": {},
            "by_member": {},
        }

        for mac in macaddresses:
            self._macaddresses["by_mac"].setdefault(str(mac.address), []).append(
                mac.member
            )
            self._macaddresses["by_member"].setdefault(mac.member.id, []).append(
                str(mac.address)
            )

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
            org_id = instance.org.remote_id
        else:
            org_id = None

        ports = devicectl.Port().objects(org=org_id)

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
                raise ValidationError(
                    _(
                        "Invalid prefix set source: {source}. Source should be `prefixctl`"
                    ).format(source=source)
                )

        except ValueError:
            raise ValidationError(
                _("Invalid prefix set slug. Format should be `prefixctl::<slug>`")
            )

        prefix_set = self.prefix_sets_by_slug.get(slug)

        if not prefix_set:
            raise ValidationError(
                _("Prefix set `{prefix_set_slug}` not found").format(
                    prefix_set_slug=prefix_set_slug
                )
            )

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

    def validate_port_quantity(self, port_quantity):
        # if lag is set, port quantity must be greater than 1
        # if lag is not set, port quantity must be 1
        # validated data is not available at this point

        lag = self.initial_data.get("lag", False)

        if not lag and port_quantity != 1:
            raise ValidationError(_("Must be 1 if LAG is not set"))

        return port_quantity

    def _validate_macaddr_limit(self, macaddr_limit, validated_data):
        """
        If ix.limit_mac_addresses is False no validation is needed

        If ix.limit_mac_addresses is True, macaddr_limit must be set
        to a value between 1 and settings.MAC_LIMIT_MAX and be greater or
        equal to the length of macaddr_set

        If ix.learned_mac_addresses is True, macaddr_set needs to be checked
        from the port.virtual_port_macaddr_set not from the data.
        """

        ix = validated_data.get("ix")

        if not ix.limit_mac_addresses:
            return 1

        if not macaddr_limit:
            raise ValidationError(_("MAC address limit is required"))

        if macaddr_limit < 1 or macaddr_limit > settings.MAC_LIMIT_MAX:
            raise ValidationError(
                _(
                    "MAC address limit must be between 1 and {settings.MAC_LIMIT_MAX}"
                ).format(settings=settings)
            )

        macaddr_set = validated_data.get("macaddr_set", [])

        if ix.learned_mac_addresses and validated_data.get("port"):
            try:
                macaddr_set = self.ports.get(
                    validated_data.get("port")
                ).virtual_port_macaddr_set
            except AttributeError:
                # member referenced a port that doesn't exist
                macaddr_set = []

        if len(macaddr_set) > macaddr_limit:
            raise ValidationError(
                {
                    "macaddr_limit": _(
                        "MAC address limit must be greater than or equal to the number of MAC addresses"
                    )
                }
            )

        return macaddr_limit

    def _validate_port_config_changes(self, validated_data: dict) -> dict:
        """
        Strict validation for port config changes.

        This is to ensure no changes are made to the port unless
        explicitly and correctly stated through the `port_config_intent`
        and the `lag`, `port_quantity`, and `port_size` fields.
        """

        member = self.instance
        intent = validated_data.get("port_config_intent")
        lag = validated_data.get("lag")
        port_quantity = validated_data.get("port_quantity")
        port_size = validated_data.get("port_size")
        port_set = validated_data.get("port_set")
        current_port_set = sorted(member.physical_ports if member else [])

        if (not member or not member or not member.port) and port_set:
            intent = validated_data["port_config_intent"] = "create"

        if not member and not port_set:
            # no physical ports selected during member creation
            # so no port config intent is needed

            intent = validated_data["port_config_intent"] = None
            return validated_data

        if intent is None:
            # if port config intent is noop and changes are made to the port
            # raise a validation error

            NOOP_ERROR = _(
                "Cannot change {field} with unspecified configuratiom intent"
            )
            validation_errors = {}
            if lag != self.instance.lag:
                validation_errors["lag"] = NOOP_ERROR.format(field="LAG")
            if port_quantity != self.instance.port_quantity:
                validation_errors["port_quantity"] = NOOP_ERROR.format(
                    field="port quantity"
                )
            if port_size != self.instance.port_size:
                validation_errors["port_size"] = NOOP_ERROR.format(field="port size")

            if validation_errors:
                raise ValidationError(validation_errors)

        elif intent == "create":
            # ensure we are actually creating a member

            if member and member.port:
                raise ValidationError(
                    {
                        "port_config_intent": _(
                            "Use `resize`, `lag-increase` or `lag-decrease` to modify an existing member port"
                        )
                    }
                )

        elif intent == "resize":
            # when resizing a port, port_set should differ from the current port_set
            # needs to account for both sets having the same elements but being
            # sorted differently

            if sorted(port_set) == current_port_set:
                raise ValidationError(
                    {
                        "port_set": _(
                            "Port set must differ from the current port set, when resizing a port."
                        )
                    }
                )

        elif intent == "lag-increase":
            # when adding physical ports to a lag we must ensure the following
            # lag = True
            # quantity > than current quantity
            # port_set contains n new ports and n is the difference between the current quantity and the new quantity
            # this comparison must be done by comparing the sets

            if not lag:
                raise ValidationError(
                    {"lag": _("LAG must be set to True when increasing LAG quantity")}
                )

            if port_quantity <= self.instance.port_quantity:
                raise ValidationError(
                    {
                        "port_quantity": _(
                            "Port quantity must be greater than the current quantity when increasing LAG quantity"
                        )
                    }
                )

            # get difference between the current port set and the new port set
            new_ports = set(port_set) - set(current_port_set)

            if len(new_ports) != port_quantity - self.instance.port_quantity:
                print(
                    f"{len(new_ports)}, {port_quantity}, {self.instance.port_quantity}, {port_set}, {current_port_set} !!!!!!!"
                )
                raise ValidationError(
                    {
                        "port_set": _(
                            "Port set must contain {n} new port(s) when increasing LAG quantity to {quantity}"
                        ).format(
                            n=port_quantity - self.instance.port_quantity,
                            quantity=port_quantity,
                        )
                    }
                )

        elif intent == "lag-decrease":
            # when removing physical ports from a lag we must ensure the following
            # lag = True (unless quantity is 1)
            # quantity < than current quantity
            # port_set contains n less ports and n is the difference between the current quantity and the new quantity
            # remaining ports must be contained in the old port set

            if not lag and port_quantity != 1:
                raise ValidationError(
                    {"lag": _("LAG must be set to True when decreasing LAG quantity")}
                )

            if port_quantity >= self.instance.port_quantity:
                raise ValidationError(
                    {
                        "port_quantity": _(
                            "Port quantity must be less than the current quantity when decreasing LAG quantity"
                        )
                    }
                )

            # get difference between the current port set and the new port set
            removed_ports = set(current_port_set) - set(port_set)

            if len(removed_ports) != self.instance.port_quantity - port_quantity:
                raise ValidationError(
                    {
                        "port_set": _(
                            "Port set must contain {n} total ports according to the provided quantity"
                        ).format(n=port_quantity)
                    }
                )

            if removed_ports - set(current_port_set):
                raise ValidationError(
                    {
                        "port_set": _(
                            "New port set must contain only ports that are part of the current port set when decreasing LAG quantity"
                        )
                    }
                )

        return validated_data

    def validate_case_number(self, case_number: str) -> str:
        # if case number is specified, so must be the work order
        if case_number and not self.initial_data.get("work_order"):
            raise ValidationError(
                "Please validate the case number and provide a work order."
            )

        # if case numbers are enabled, case_number is required
        # when making port assignment changes
        intent = self.initial_data.get("port_config_intent")
        port_set = self.initial_data.get("port_set")
        member = self.instance
        if (not member or not member or not member.port) and port_set:
            intent = "create"
        if (
            intent in ["create", "resize", "lag-increase", "lag-decrease"]
            and not case_number
        ):
            raise ValidationError(_("Required when making port assignment changes."))

        return case_number

    def validate(self, data: dict) -> dict:
        # if case numbers are enabled push them into meta under
        # a case_number key (list)

        if settings.MEMBER_CASE_NUMBERS_ENABLED:
            case_number = data.get("case_number")
            work_order = data.get("work_order")
            meta = data.get("meta", {})
            if case_number:
                meta.setdefault("case_number", []).append(case_number)
                meta.setdefault("work_order", []).append(work_order)
                data["meta"] = meta
            self._case_number = data.pop("case_number", None)
            self._work_order = data.pop("work_order", None)

        # validate macaddr_limit
        data["macaddr_limit"] = self._validate_macaddr_limit(
            data.get("macaddr_limit"), data
        )

        # validate port config changes
        data = self._validate_port_config_changes(data)

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
            if data.get("meta") and "work_order" in data.get("meta"):
                del data.meta["work_order"]

        # if the parent ix has learned mac addresses enabled
        # we want to substitute the macaddr_set with the mac addresses
        # from port.virtual_port_macaddr_set

        if instance.ix.learned_mac_addresses:
            if instance.port and self.ports.get(instance.port.id):
                data["macaddr_set"] = self.ports.get(
                    instance.port.id
                ).virtual_port_macaddr_set
            else:
                data["macaddr_set"] = []
            data["macaddr"] = data["macaddr_set"][0] if data["macaddr_set"] else None

        # if the parent ix has turned off limit_mac_addresses
        # set mac_addr_limit to None
        if not instance.ix.limit_mac_addresses:
            data["macaddr_limit"] = None

        return data

    def save(self):
        # these need to be popped before saving the member, otherwise
        # drf will pass them as kwargs to the save method
        intent = self.validated_data.pop("port_config_intent", None)
        port_set = self.validated_data.pop("port_set", [])

        member = super().save()
        # member needs to be saved before we can set the macaddr_set
        member.macaddr_set = self.validated_data.get("macaddr_set", [])

        # preload ports
        models.InternetExchangeMember.preload_ports(member.org, [member])

        port_automation.handle_port_assignment(
            intent,
            port_set,
            member,
            meta={
                "case_number": getattr(self, "_case_number", None),
                "work_order": getattr(self, "_work_order", None),
            },
        )

        if member.port:
            if intent:
                member.port.load()
            port_automation.sync_ip_addresses(member)

        return member

    def get_prefix_set_name(self, obj):
        if not obj.prefix_set:
            return None

        prefix_set = self.prefix_sets_by_slug.get(obj.prefix_set_slug)

        if not prefix_set:
            return None

        return prefix_set.name

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
        # if mac addresses are learned from the port, we don't need to check for duplicates
        if obj.ix.learned_mac_addresses:
            return []

        # collect member's mac addresses from self.macaddresses
        macaddr_set = self.macaddresses["by_member"].get(obj.id, [])

        if not macaddr_set:
            return []

        warnings = []

        for macaddr in macaddr_set:
            warnings.extend(
                [
                    f"MAC address {macaddr} also exists on AS{member.asn} - {member.ipaddr4}"
                    for member in self.macaddresses["by_mac"].get(macaddr, [])
                    if member.id != obj.id
                ]
            )

        return warnings


@register
class InternetExchangeMemberValidationRequest(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    # these numeric fields are set to char type,
    # because we're executing the validation logic
    # inside the task, not through the serializer.
    asn = serializers.CharField(required=False, allow_blank=True, allow_null=True)
    port = serializers.CharField(required=False, allow_blank=True, allow_null=True)

    if settings.MEMBER_CASE_NUMBERS_ENABLED:
        case_number = serializers.CharField(
            required=False, allow_blank=True, allow_null=True
        )

    ref_tag = "member_validation_request"

    class Meta:
        fields = ["name", "asn"]
        if settings.MEMBER_CASE_NUMBERS_ENABLED:
            fields.append("case_number")


@register
class InternetExchangeMemberValidationResult(ModelSerializer):
    ref_tag = "member_validation_result"

    class Meta:
        model = Task
        fields = ["id", "op", "status", "result", "error"]

    def validate(self, validated_data: dict):
        """
        Loads the task object and checks that the `op` is
        a valid member validation task
        """

        valid_task_ops = [
            "task_get_next_ipv4",
            "task_verify_organization",
            "task_verify_case_number",
        ]

        task = self.instance

        if task.op not in valid_task_ops:
            raise ValidationError("Invalid task")


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

    def validate(self, validated_data: dict) -> dict:
        """
        Router ID must be unique per organization
        """

        ix = validated_data.get("ix")
        router_id = validated_data.get("router_id")

        qset = models.Routeserver.objects.filter(
            ix__instance__org=ix.instance.org, router_id=router_id
        )

        if self.instance and self.instance.id:
            qset = qset.exclude(id=self.instance.id)

        if qset.exists():
            raise ValidationError(
                {"router_id": _("Router ID already exists for this organization")}
            )

        return validated_data

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


@register
class TrafficAlertConfigSerializer(ModelSerializer):
    ref_tag = "traffic_alert_config"

    class Meta:
        model = models.TrafficAlertConfig
        fields = "__all__"

    def validate(self, data):
        validated_data = super().validate(data)
        member_emails_max_frequency = validated_data.get("member_emails_max_frequency")
        operator_emails_max_frequency = validated_data.get(
            "operator_emails_max_frequency"
        )

        if validated_data.get("operator_emails") and not operator_emails_max_frequency:
            raise ValidationError(_("You must set a frequency for operator emails."))

        if validated_data.get("member_emails") and not member_emails_max_frequency:
            raise ValidationError(_("You must set a frequency for member emails."))

        return validated_data


@register
class EmailTemplate(ModelSerializer):
    ref_tag = "email_template"

    class Meta:
        model = models.EmailTemplate
        fields = "__all__"


@register
class TemplatePreview(serializers.Serializer):
    ref_tag = "template_preview"

    body = serializers.SerializerMethodField()

    class Meta:
        fields = ["body"]

    def get_body(self, obj):
        try:
            return obj.render()
        except Exception as exc:
            return (
                "!!! ERROR !!!\nWhen trying to render the template "
                f"we encountered the following issue:\n\n{exc}\n\nPlease fix and try again."
            )


@register
class Device(serializers.Serializer):
    ref_tag = "device"
    name = serializers.CharField()
    id = serializers.IntegerField()

    class Meta:
        fields = ["name", "id"]


@register
class MemberStat(serializers.Serializer):
    ref_tag = "member_stat"

    member_id = serializers.IntegerField()
    bgp_stat = serializers.DictField()
    traffic_alert_data = serializers.DictField()

    class Meta:
        fields = "__all__"
