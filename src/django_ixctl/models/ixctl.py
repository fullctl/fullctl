import ipaddress
import os.path
import re
import subprocess
import tempfile
from datetime import datetime
from secrets import token_urlsafe

try:
    from pydantic.utils import deep_update
except ImportError:
    from pydantic.v1.utils import deep_update

try:
    from yaml import CDumper as Dumper
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Dumper, Loader

import fullctl.service_bridge.auditctl as auditctl
import fullctl.service_bridge.devicectl as devicectl
import fullctl.service_bridge.pdbctl as pdbctl
import fullctl.service_bridge.prefixctl as prefixctl
import fullctl.service_bridge.sot as sot
import reversion
import structlog
import yaml
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django_grainy.decorators import grainy_model
from django_inet.models import ASNField
from fullctl.django.fields.service_bridge import (
    ReferencedObjectField,
    ReferencedObjectUUIDField,
)
from fullctl.django.inet.validators import validate_as_set
from fullctl.django.models.abstract.base import HandleRefModel, PdbRefModel
from fullctl.django.models.abstract.template import TemplateModel
from fullctl.django.models.concrete import Instance, Organization
from netfields import CidrAddressField, InetAddressField, MACAddressField

import django_ixctl.enum
import django_ixctl.models.tasks
from django_ixctl.models.util import set_port_fields_from_speed
from django_ixctl.validators import validate_ix_config

logger = structlog.get_logger(__name__)


def generate_secret():
    return token_urlsafe()


def get_as_set(as_set_string):
    return [as_set.strip() for as_set in re.split(r"[, ]+", as_set_string)]


@reversion.register
@grainy_model(namespace="org")
class PermissionRequest(HandleRefModel):
    org = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="permreq_set"
    )
    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, related_name="permreq_set"
    )
    type = models.CharField(
        max_length=255,
        choices=django_ixctl.enum.PERMISSION_REQUEST_TYPES,
    )
    extra = models.TextField(null=True, blank=True)

    class HandleRef:
        tag = "permreq"

    class Meta:
        db_table = "ixctl_permreq"
        verbose_name = _("Permission Request")
        verbose_name_plural = _("Permission Requests")

    def __str__(self):
        return f"Permission Request: {self.user} -> {self.org}"


@reversion.register()
@grainy_model(
    namespace="ix", namespace_instance="ix.{instance.org.permission_id}.{instance.id}"
)
class InternetExchange(PdbRefModel):

    """
    Describes an internet exchange

    Can have a reference to a peeringdb ixlan object
    """

    name = models.CharField(max_length=255, blank=False)
    created = models.DateTimeField(auto_now_add=True)
    updated = models.DateTimeField(auto_now=True)
    urlkey = models.CharField(max_length=255, default=generate_secret, unique=True)
    ixf_export_privacy = models.CharField(
        max_length=32,
        choices=django_ixctl.enum.IXF_EXPORT_PRIVACY_TYPES,
        default="public",
    )

    slug = models.SlugField(max_length=64, unique=False, blank=False, null=False)

    instance = models.ForeignKey(
        Instance, related_name="ix_set", on_delete=models.CASCADE, null=True
    )

    verified = models.BooleanField(
        default=False, help_text=_("Exchange ownership has been verified")
    )
    notes = models.TextField(null=True, blank=True, help_text=_("Notes"))
    public_view = models.BooleanField(default=False)

    source_of_truth = models.BooleanField(
        default=False,
        help_text=_(
            "Allows other fullctl services to see ixctl as the source of truth for this exchange"
        ),
    )

    limit_mac_addresses = models.BooleanField(
        default=False, help_text=_("Limit MAC addresses")
    )

    learned_mac_addresses = models.BooleanField(
        default=False, help_text=_("MAC addresses are learned from devicectl")
    )

    mtu = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text=_("MTU for the exchange"),
    )

    vlan_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("VLAN ID for the exchange"),
    )

    # TODO: use service-bridge reference field?
    # this field is already defined through PdbRefModel, however we need to
    # override it here to give it a help-text
    pdb_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_(
            "PeeringDB id of the equivalent exchange (`ix`) object on their end. Its important to set this when the exchange has the source of truth in fullctl so we know which peeringdb object to override. This is set automatically if the ix was imported from peeringdb."
        ),
    )

    graph_traffic_source = models.CharField(
        max_length=255,
        choices=(
            ("", "No Graphs"),
            ("rrd_mrtg", "RRD / MRTG (deprecated)"),
            ("vm_mrtg", "VictoriaMetrics / MRTG"),
            ("vm_sflow", "VictoriaMetrics / sFlow"),
        ),
        help_text=_("Traffic metric storage and data type for graph rendering"),
        default="",
        blank=True,
    )

    config = models.JSONField(
        null=True,
        blank=True,
        default=dict,
        help_text=_("Extra ix specific configuration"),
        validators=[validate_ix_config],
    )

    traffic_poll_time = models.PositiveSmallIntegerField(
        default=300,
        help_text=_("Time interval to poll traffic data in seconds."),
        validators=[MinValueValidator(1)],
    )

    class PdbRef(PdbRefModel.PdbRef):
        pdbctl = pdbctl.InternetExchange

    class HandleRef:
        tag = "ix"

    class Meta:
        db_table = "ixctl_ix"
        verbose_name_plural = _("Internet Exchanges")
        verbose_name = _("Internet Exchange")
        constraints = [
            models.UniqueConstraint(
                fields=["instance", "slug"], name="unique_slug_instance_pair"
            )
        ]

    @classmethod
    def create_from_pdb(cls, instance, pdb_object, save=True, **fields):
        """
        create instance from peeringdb ixlan

        Argument(s):

        - instance (`Instance`): instance that contains this exchange
        - pdb_object (`fullctl.service_bridge.pdbctl.IXLan`): pdb ixlan instance
        - save (`bool`): if True commit to the database, otherwise dont

        Keyword Argument(s):

        Any arguments passed will be used to set properties on the
        object before creation

        Returns:

        - `InternetExchange` instance
        """

        ix = super().create_from_pdb(pdb_object, save=save, instance=instance, **fields)

        ix.name = pdb_object.name
        ix.slug = cls.default_slug(ix.name)
        ix.mtu = pdb_object.mtu

        if save:
            ix.save()

        # create members from pdb

        for netixlan in pdbctl.NetworkIXLan().objects(ix=pdb_object.id, join="net"):
            InternetExchangeMember.create_from_pdb(netixlan, ix=ix)

        # create prefixes from pdb

        pdb_prefixes = pdbctl.IXLanPrefix().objects(ix=pdb_object.id)

        for prefix in pdb_prefixes:
            InternetExchangePrefix.objects.create(ix=ix, prefix=prefix.prefix)

        return ix

    @classmethod
    def default_slug(cls, name):
        return (
            name.replace("/", "_")
            .replace(" ", "_")
            .replace(".", "_")
            .replace("-", "_")
            .lower()
        )

    @classmethod
    def get_default_exchange_for_org(cls, org):
        """
        Returns the default exchange for an organization

        Will return the default exchange for the organization if
        specified, otherwise will return the first exchange in the
        organization's instance.

        If the organization has no exchanges in its instance, will
        return None
        """

        try:
            return OrganizationDefaultExchange.objects.get(org=org).ix
        except OrganizationDefaultExchange.DoesNotExist:
            return cls.objects.filter(instance__org=org).first()

    @classmethod
    def set_default_exchange_for_org(cls, org, ix):
        """
        Will take an Organization object and make the specified
        InternetExchange the default exchange for that organization
        """

        # check that ix belongs to org

        if ix.org != org:
            raise ValueError("InternetExchange does not belong to Organization")

        try:
            default = OrganizationDefaultExchange.objects.get(org=org)
        except OrganizationDefaultExchange.DoesNotExist:
            default = OrganizationDefaultExchange(org=org)

        default.ix = ix
        default.save()

    @property
    def display_name(self):
        """
        Will return the exchange name if specified.

        If self.name is not specified and pdb reference is set return
        the name of the peeringdb ix instead

        If peeringdb reference is not specified either, return
        generic "Nameless Exchange ({id})"
        """

        if self.name:
            return self.name
        if self.pdb_id:
            return self.pdb.ix.name
        return f"Nameless Exchange ({self.id})"

    @property
    def ixf_export_url(self):
        """
        Returns the path for the ix-f export URL for this
        exchange
        """

        return reverse(
            "ixf export",
            args=(
                self.instance.org.slug,
                self.slug,
            ),
        )

    @property
    def org(self):
        return self.instance.org

    @property
    def port_sizes(self):
        # check self.configs["port_sizes"] first
        # if not set, return settings.PORT_SIZES
        if not self.config:
            return settings.PORT_SIZES

        return self.config.get("port_sizes") or settings.PORT_SIZES

    @property
    def facilities(self) -> list[str]:
        # check self.config["facilities"]
        # if not set, return []
        if not self.config:
            return []

        return self.config.get("facilities") or []

    def __str__(self):
        return f"{self.name} ({self.id})"


@grainy_model(
    namespace="ix",
    namespace_instance="ix.{instance.org.permission_id}.{instance.ix_id}.prefix",
)
class InternetExchangePrefix(HandleRefModel):
    """
    Describes a CIDR prefix for an internet exchange
    """

    ix = models.ForeignKey(
        InternetExchange,
        related_name="prefixes",
        on_delete=models.CASCADE,
    )

    prefix = CidrAddressField()

    class Meta:
        db_table = "ixctl_prefix"
        verbose_name = _("Internet Exchange Prefix")
        verbose_name_plural = _("Internet Exchange Prefixes")
        unique_together = (("prefix", "ix"),)

    class HandleRef:
        tag = "prefix"

    @property
    def org(self):
        return self.ix.instance.org

    def __str__(self):
        return f"{self.prefix} - {self.ix.name}"


class OrganizationDefaultExchange(models.Model):
    """
    Describes the default exchange for an organization

    This is used to determine which exchange to use when
    no exchange is specified in the url.
    """

    org = models.OneToOneField(
        Organization,
        related_name="default_ix",
        on_delete=models.CASCADE,
        primary_key=True,
    )
    ix = models.OneToOneField(
        InternetExchange,
        related_name="default_for_org",
        on_delete=models.CASCADE,
    )

    class Meta:
        db_table = "ixctl_default_ix"
        verbose_name = _("Organization Default Exchange")
        verbose_name_plural = _("Organization Default Exchanges")

    def __str__(self):
        return f"{self.org.name} -> {self.ix.name}"


@reversion.register()
@grainy_model(
    namespace="member",
    namespace_instance=(
        "member.{instance.org.permission_id}.{instance.ix_id}.{instance.asn}"
    ),
)
class InternetExchangeMember(PdbRefModel):

    """
    Describes a member at an internet exchange

    Can have a reference to a peeringdb netixlan object
    """

    ix = models.ForeignKey(
        InternetExchange,
        help_text=_("Members at this Exchange"),
        related_name="member_set",
        on_delete=models.CASCADE,
    )
    ipaddr4 = InetAddressField(blank=True, null=True, store_prefix_length=False)
    ipaddr6 = InetAddressField(blank=True, null=True, store_prefix_length=False)
    as_macro_override = models.CharField(
        max_length=255, blank=True, null=True, validators=[validate_as_set]
    )
    as_macro_negate = models.BooleanField(default=False)
    md5 = models.CharField(max_length=255, null=True, blank=True)
    is_rs_peer = models.BooleanField(default=False)

    port_size = models.PositiveIntegerField(
        help_text=_("Port size"),
        # we cannot set a default, since the valid choices may vary
        # depending on the exchange or the settings.PORT_SIZES value
    )

    port_quantity = models.PositiveSmallIntegerField(
        default=1,
        help_text=_("Number of ports"),
        choices=[(i, str(i)) for i in range(1, settings.PORT_LIMIT_MAX + 1)],
    )

    lag = models.BooleanField(default=False)

    macaddr_limit = models.PositiveSmallIntegerField(
        help_text=_("MAC limit - if the parent ix is set to use MAC limiting"),
        default=1,
    )

    asn = models.PositiveIntegerField()
    name = models.CharField(max_length=255, blank=True, null=True)
    prefix_set = models.CharField(
        null=True,
        blank=True,
        help_text=_("URI for accessing a prefixlist, currently prefixctl::$slug"),
    )

    ixf_state = models.CharField(
        max_length=255, default="active", choices=django_ixctl.enum.MEMBER_STATE
    )
    ixf_member_type = models.CharField(
        max_length=255, choices=django_ixctl.enum.IXF_MEMBER_TYPE, default="peering"
    )

    port = ReferencedObjectField(
        bridge=devicectl.Port,
        null=True,
        blank=True,
        help_text=_("deviceCtl port reference"),
    )

    status = models.CharField(
        max_length=12, default="ok", choices=django_ixctl.enum.PORT_STATE
    )

    meta = models.JSONField(
        null=True, blank=True, help_text=_("Meta data"), default=dict
    )

    class PdbRef(PdbRefModel.PdbRef):
        pdbctl = pdbctl.NetworkIXLan

    class HandleRef:
        tag = "member"

    class Meta:
        db_table = "ixctl_member"
        verbose_name_plural = _("Internet Exchange Members")
        verbose_name = _("Internet Exchange Member")
        unique_together = (("ipaddr4", "ix"), ("ipaddr6", "ix"))

    @classmethod
    def create_from_pdb(cls, pdb_object, ix, save=True, **fields):
        """
        Create `InternetExchangeMember` from peeringdb netixlan

        Argument(s):

        - pdb_object (`fullctl.service_bridge.pdbctl.NetworkIXLan`): netixlan instance
        - ix (`InternetExchange`): member of this ix

        Keyword Argument(s):

        And keyword arguments passwed will be used to inform properties
        of the InternetExchangeMember to be created
        """

        member = super().create_from_pdb(pdb_object, ix=ix, save=False, **fields)

        member.ipaddr4 = pdb_object.ipaddr4
        member.ipaddr6 = pdb_object.ipaddr6
        member.is_rs_peer = pdb_object.is_rs_peer
        member.asn = pdb_object.net.asn
        member.name = pdb_object.net.name

        set_port_fields_from_speed(member, pdb_object.speed)

        if save:
            member.save()

        return member

    @classmethod
    def preload_networks(cls, queryset):
        """
        Preloads network information from peerctl and pdbctl
        """

        asns = {member.asn for member in queryset}
        if not asns:
            return queryset
        asn_map = {}
        for net in sot.Network().objects(asns=list(asns)):
            asn_map[net.asn] = net

        for member in queryset:
            member._net = asn_map.get(member.asn)
            yield member

    @classmethod
    def preload_ports(cls, org, members):
        """
        Preloads devicectl port information

        Argument(s):

        - org (`Organization`): organization to load ports for
        - members (`list` of `InternetExchangeMember`): members to load ports for
        """

        if len(members) > 1:
            # we got multiple members, so we batch load all ports for the org
            ports = list(
                devicectl.Port().objects(
                    org_slug=org.slug, join=["device", "physical_ports"]
                )
            )
        elif len(members) == 1:
            # we got a single member, so we load only the port for that member
            member = members[0]
            if not member.port:
                return
            ports = list(
                devicectl.Port().objects(
                    org_slug=org.slug,
                    id=int(member.port),
                    join=["device", "physical_ports"],
                )
            )
        else:
            return

        if not ports:
            return

        # restructure ports into dict keyed by port id

        ports = {port.id: port for port in ports}

        for member in members:
            if not member.port:
                continue

            port = ports.get(int(member.port))

            if not port:
                continue

            member.port._object = port

    @classmethod
    def set_ports_status(cls, member, status: str):
        """
        Update the status of a member's ports in deviceCtl.

        Args:
            member: The member object that contains the `port` attribute.
            status (str): The new status to be applied to the member's port.

        Returns:
            None
        """
        if not member.port:
            return

        member.status = status
        member.save()

        devicectl.Port().set_ports_status(status=status, pk=member.port.id)

    @property
    def display_name(self):
        return self.name or f"AS{self.asn}"

    @property
    def org(self):
        return self.ix.instance.org

    @property
    def ix_name(self):
        return self.ix.name

    @property
    def as_sets(self):
        if not self.as_macro:
            return []

        return get_as_set(self.as_macro)
        # return [as_set.strip() for as_set in re.split(r"[, ]+", self.as_macro)]

    @property
    def speed(self) -> int:
        """
        Calculates speed from port_size * port_quantity

        Returns speed in Mb.

        Port size is in Gb so we multiply by 1000.
        """

        if self.port_size is None:
            return 0

        return self.port_size * self.port_quantity * 1000

    @property
    def as_macro(self):
        if self.as_macro_negate is True:
            return ""

        if self.as_macro_override:
            return self.as_macro_override

        if self.net:
            if self.net.source == "peerctl":
                return self.net.as_set
            elif self.net.source == "pdbctl":
                return self.net.irr_as_set
        return ""

    @property
    def prefix4(self):
        if self.net:
            if self.net.source == "peerctl":
                return self.net.prefix4
            elif self.net.source == "pdbctl":
                return self.net.info_prefixes4
        return 0

    @property
    def prefix6(self):
        if self.net:
            if self.net.source == "peerctl":
                return self.net.prefix6
            elif self.net.source == "pdbctl":
                return self.net.info_prefixes6
        return 0

    @property
    def net(self):
        if hasattr(self, "_net"):
            return self._net

        self._net = sot.Network().first(asn=self.asn)
        return self._net

    @property
    def prefix_set_source(self) -> str | None:
        """
        Returns the source of the prefix set if set (e.g., prefixctl)
        None if not set

        This seems redundant currently, since the only source
        for prefix sets is prefixctl
        """

        if not self.prefix_set:
            return None

        return self.prefix_set.split("::")[0]

    @property
    def prefix_set_slug(self) -> str | None:
        """
        Returns the slug of the prefix set if set
        None if not set
        """

        if not self.prefix_set:
            return None

        return self.prefix_set.split("::")[-1]

    @property
    def macaddr(self) -> str | None:
        """
        Backwards compatibility for macaddr field
        """

        try:
            return str(self.mac_addresses.all()[0].address)
        except IndexError:
            return None

    # setter for macaddr field
    @macaddr.setter
    def macaddr(self, value: str):
        if not value or not self.id:
            return

        self.mac_addresses.all().delete()

        MacAddress.objects.get_or_create(member=self, address=value)

    @property
    def macaddr_set(self) -> list[str]:
        """
        Returns a list of MAC addresses for this member
        """

        return [str(mac.address) for mac in self.mac_addresses.all()]

    # setter for macaddr_set field
    @macaddr_set.setter
    def macaddr_set(self, macs: list[str]):
        if not self.id:
            return

        # delete all existing mac addresses
        self.mac_addresses.all().delete()

        if not macs:
            return

        self.mac_addresses.bulk_create(
            MacAddress(member=self, address=mac) for mac in macs
        )

    @property
    def physical_ports(self) -> list[int]:
        """
        If port is set, return a list of physical port ids through
        port.physical_ports
        """

        if not self.port or not self.port.object.physical_ports:
            return []

        return [port["id"] for port in self.port.object.physical_ports]

    def __str__(self):
        return f"AS{self.asn} - {self.ipaddr4} - {self.ipaddr6} ({self.id})"


@reversion.register()
@grainy_model(
    namespace="member",
    namespace_instance=(
        "member.{instance.org.permission_id}.{instance.ix_id}.{instance.member.asn}"
    ),
)
class MacAddress(HandleRefModel):

    """
    Describes a MAC address
    """

    address = MACAddressField()
    member = models.ForeignKey(
        InternetExchangeMember,
        on_delete=models.CASCADE,
        related_name="mac_addresses",
    )

    class Meta:
        db_table = "ixctl_mac"
        verbose_name = _("MAC Address")
        verbose_name_plural = _("MAC Addresses")
        unique_together = (("address", "member"),)

    class HandleRef:
        tag = "mac"

    def __str__(self):
        return f"{self.address}"


@reversion.register
@grainy_model(
    namespace="rs",
    namespace_instance=(
        "routeserver.{instance.org.permission_id}.{instance.ix_id}.{instance.asn}"
    ),
)
class Routeserver(HandleRefModel):

    """
    Describes a routeserver at an internet exchange
    """

    ix = models.ForeignKey(
        InternetExchange,
        on_delete=models.CASCADE,
        related_name="rs_set",
    )

    # RS Config

    name = models.CharField(
        max_length=255,
        help_text=_("Routeserver name"),
    )

    asn = ASNField(help_text=_("ASN"))

    router_id = InetAddressField(
        store_prefix_length=False,
        help_text=_("Router Id"),
    )

    rpki_bgp_origin_validation = models.BooleanField(default=False)

    # ARS Config

    ars_type = models.CharField(
        max_length=32,
        choices=django_ixctl.enum.ARS_TYPES,
        default="bird",
    )

    max_as_path_length = models.IntegerField(
        default=32,
        help_text=_("Max length of AS_PATH attribute."),
    )

    no_export_action = models.CharField(
        max_length=8,
        choices=django_ixctl.enum.ARS_NO_EXPORT_ACTIONS,
        default="pass",
        help_text=_("RFC1997 well-known communities (NO_EXPORT and NO_ADVERTISE)"),
    )

    graceful_shutdown = models.BooleanField(
        default=False,
        help_text=_("Graceful BGP session shutdown"),
    )

    operational_status = models.CharField(
        max_length=32,
        choices=django_ixctl.enum.OPERATIONAL_STATUS_CHOICES,
        default="operational",
    )

    extra_config = models.TextField(
        null=True, blank=True, help_text=_("Extra arouteserver config")
    )

    event = ReferencedObjectUUIDField(
        bridge=auditctl.Event,
        null=True,
        blank=False,
        help_text=_("auditCtl event reference"),
    )

    class Meta:
        db_table = "ixctl_rs"
        unique_together = (("ix", "router_id"), ("ix", "name"))

    class HandleRef:
        tag = "routeserver"

    @property
    def org(self):
        return self.ix.instance.org

    @property
    def display_name(self):
        return self.name

    @property
    def routeserver_config(self):
        """
        Return the routeserver_config instance for this routeserver

        Will create the routeserver_config instance if it does not exist yet
        """
        if not hasattr(self, "_routeserver_config"):
            routeserver_config, created = RouteserverConfig.objects.get_or_create(
                routeserver=self
            )
            self._routeserver_config = routeserver_config
        return self._routeserver_config

    @property
    def routeserver_config_status_dict(self):
        """
        Returns a status dict for the current state of this routeserver's
        configuration
        """

        routeserver_config = self.routeserver_config

        task = routeserver_config.task

        # no status

        if not task and not routeserver_config.rs_response:
            return {"status": None}

        if not task:
            return routeserver_config.rs_response

        if task.status == "pending":
            return {"status": "queued"}
        if task.status == "running":
            return {"status": "generating"}
        if task.status == "cancelled":
            return {"status": "canceled"}
        if task.status == "failed":
            return {"status": "error", "error": task.error}
        if task.status == "completed":
            if not routeserver_config.rs_response:
                return {"status": "generated"}
            return routeserver_config.rs_response

        return {"status": None}

    @property
    def routeserver_config_status(self):
        return self.routeserver_config_status_dict.get("status")

    @property
    def routeserver_config_generated_time(self):
        return self.routeserver_config.generated

    @property
    def routeserver_config_response(self):
        return self.routeserver_config.rs_response

    @property
    def routeserver_config_error(self):
        return self.routeserver_config_status_dict.get("error")

    @property
    def ars_general(self):
        """
        Generate and return `dict` for ARouteserver general config
        """

        ars_general = {
            "cfg": {
                "rs_as": self.asn,
                "router_id": f"{self.router_id}",
                "filtering": {
                    "max_as_path_len": self.max_as_path_length,
                    "rpki_bgp_origin_validation": {
                        "enabled": self.rpki_bgp_origin_validation
                    },
                },
                "rfc1997_wellknown_communities": {
                    "policy": self.no_export_action,
                },
                "graceful_shutdown": {"enabled": self.graceful_shutdown},
            }
        }

        if self.extra_config:
            extra_config = yaml.load(self.extra_config, Loader=Loader)

            # TODO: should we expect people to put the cfg:
            # root element into the extra config or not ?
            #
            # support both approaches for now

            # use deep_update instead of update to prevent overriding of nested dicts
            if "cfg" in extra_config:
                ars_general["cfg"] = deep_update(
                    ars_general["cfg"], extra_config["cfg"]
                )
            else:
                ars_general = deep_update(ars_general, extra_config)

        return ars_general

    @property
    def ars_clients(self):
        """
        Generate and return `dict` for ARouteserver clients config
        """

        asns = []
        asn_as_sets = {}
        clients = {}

        # TODO
        # where to get ASN sets from ??
        # peeringdb network ??
        rs_peers = InternetExchangeMember.preload_networks(
            self.ix.member_set.filter(is_rs_peer=True)
        )

        for member in rs_peers:
            if member.asn not in asns:
                asns.append(member.asn)
            if member.asn not in clients:
                clients[member.asn] = {"asn": member.asn, "ip": [], "cfg": {}}

            if member.ipaddr4:
                clients[member.asn]["ip"].append(f"{member.ipaddr4}")

            if member.ipaddr6:
                clients[member.asn]["ip"].append(f"{member.ipaddr6}")

            if member.as_macro:
                clients[member.asn]["cfg"].update(
                    filtering={
                        "irrdb": {
                            "as_sets": member.as_sets,
                        }
                    }
                )

            if member.md5:
                clients[member.asn]["password"] = f"{member.md5}"

        # these aren't needed since they're already defined from SoT in the
        # more specific members list
        #
        # if asns:
        #     for net in pdbctl.Network().objects(asns=asns):
        #         if net.irr_as_set:
        #             asn_as_sets[f"AS{net.asn}"] = {
        #                 "as_sets": get_as_set(net.irr_as_set)
        #             }

        ars_clients = {"asns": asn_as_sets, "clients": list(clients.values())}

        self.configure_whitelist_routes(ars_clients)
        return ars_clients

    def __str__(self):
        return f"Routeserver {self.name} AS{self.asn}"

    def configure_whitelist_routes(self, ars_clients: dict):
        """
        Configures whitelist routes for clients

        Excpects ars_clients to be the return value of `self.ars_clients` (arouteserver
        clients config, containing the `clients` key)

        See https://arouteserver.readthedocs.io/en/latest/CONFIG.html#white-lists
        """

        # load members with prefix sets and store by ASN
        members = {
            member.asn: member
            for member in self.ix.member_set.filter(prefix_set__isnull=False)
        }

        if not members:
            return

        # load prefix sets from prefixctl and store by slug
        prefix_sets = {
            prefix_set.slug: prefix_set
            for prefix_set in prefixctl.PrefixSet().objects(
                org=self.org.slug,
                slugs=[member.prefix_set_slug for member in members.values()],
            )
        }

        for client in ars_clients["clients"]:
            member = members.get(client["asn"])

            if not member:
                # member does not have a prefix set configured
                continue

            # ars_clients is built from members so we don't need
            # to check if member exists

            prefix_set = prefix_sets.get(member.prefix_set_slug)

            if not prefix_set:
                logger.warning(f"Prefix set `{member.prefix_set_slug}` not found")
                continue

            if not prefix_set.prefixes:
                logger.warning(f"Prefix set `{member.prefix_set_slug}` has no prefixes")
                continue

            client["cfg"].setdefault("filtering", {}).setdefault("irrdb", {})[
                "white_list_route"
            ] = []

            for _prefix in prefix_set.prefixes:
                prefix = ipaddress.ip_network(_prefix["prefix"])
                white_list_route = client["cfg"]["filtering"]["irrdb"][
                    "white_list_route"
                ]
                white_list_route.append(
                    {
                        "prefix": str(prefix),
                        "asn": member.asn,
                        "length": prefix.prefixlen,
                    }
                )

    @classmethod
    def preload_events(cls, routeservers):
        """
        Preloads auditctl event information

        Argument(s):
        - routeservers (`list` of `RouteServer`): routeservers to load events for
        """
        event_ids = [
            str(routeserver.event) for routeserver in routeservers if routeserver.event
        ]
        if not event_ids:
            return

        events = auditctl.Event().get_events_by_ids(event_ids=event_ids)
        if not events:
            return

        events = {event.id: event for event in events}
        for routeserver in routeservers:
            if not routeserver.event:
                continue

            event = events.get(str(routeserver.event))
            if not event:
                continue

            routeserver._event_object = event


@reversion.register
class RouteserverConfig(HandleRefModel):

    """
    Describes a configuration (arouteserver generated) for a
    `Routeserver` instance
    """

    routeserver = models.OneToOneField(
        Routeserver,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    generated = models.DateTimeField(
        auto_now=True, blank=True, help_text=_("Time of generation")
    )

    # TODO: rename to `config` ?
    # Once we have confu backed config fields
    # i sort of want the `config` attribute to be
    # reserved for confu config fields though.

    body = models.TextField(help_text=_("Config content"))

    ars_general = models.TextField(
        help_text=("ARouteserver general config"), null=True, blank=True
    )
    ars_clients = models.TextField(
        help_text=("ARouteserver clients config"), null=True, blank=True
    )

    doc_md = models.TextField(
        help_text=("ARouteserver markdown"), null=True, blank=True
    )

    rs_response = models.JSONField(
        help_text=("Routeserver response"), null=True, blank=True
    )

    task = models.ForeignKey(
        "django_ixctl.RsConfGenerate",
        on_delete=models.CASCADE,
        related_name="routeserver_config_set",
        blank=True,
        null=True,
        help_text=_(
            "Reference to most recent generate task for this routeserver_config object"
        ),
    )

    class HandleRef:
        tag = "config.routeserver"

    class Meta:
        db_table = "ixctl_rsconf"

    @property
    def outdated(self):
        """
        Returns whether or not the config needs to be regenerated
        """

        # Route server has been updated since last generation,

        if not self.generated or self.generated < self.routeserver.updated:
            return True

        # RS Peer has been updated since last generation

        for member in self.routeserver.ix.member_set.filter(is_rs_peer=True):
            if self.generated < member.updated:
                return True
        return False

    def queue_generate(self):
        """
        Queue task to regenerate config
        """
        self.task = django_ixctl.models.tasks.RsConfGenerate.create_task(self.id)
        self.rs_response = {}
        self.save()

    def run_ars_command(
        self,
        operation: str,
        general_config_file: str,
        clients_config_file: str,
        output_file: str | None,
        extra_params: list[str] = None,
        timeout: int = 600,
    ):
        """
        Run arouteserver command

        Arguments:

        - operation (`str`): arouteserver operation
            This could be an ars type like `bird` or `md` for generating
            a markdown file
        - general_config_file (`str`): path to general config file
        - clients_config_file (`str`): path to clients config file
        - output_file (`str`): path to output file
        - extra_params (`list` of `str`): extra parameters to passthrough to
            subprocess.Popen command line
        - timeout (`int`): timeout for the command (in seconds)
        """

        cmd = [
            "arouteserver",
            operation,
            "--general",
            general_config_file,
            "--clients",
            clients_config_file,
        ]

        if extra_params:
            cmd += extra_params

        if output_file:
            cmd += ["-o", output_file]

        logger.debug("running ARS command", cmd=cmd)

        process = subprocess.Popen(cmd, stderr=subprocess.PIPE)
        _, err = process.communicate(timeout=timeout)

        if process.returncode:
            if err:
                err = err.decode("utf-8")
                raise OSError(err)
            else:
                raise OSError(f"Process returned {process.returncode}")

    def generate_markdown(
        self, general_config_file: str, clients_config_file: str, output_file: str
    ):
        """
        Generates device markdown information using arouteserver

        Arguments:

        - general_config_file (`str`): path to general config file
        - clients_config_file (`str`): path to clients config file
        - output_file (`str`): path to output markdown file
        """

        self.run_ars_command(
            "md",
            general_config_file,
            clients_config_file,
            output_file,
        )

        with open(output_file) as fh:
            self.doc_md = fh.read()

    def generate_config(
        self,
        ars_type: str,
        general_config_file: str,
        clients_config_file: str,
        output_file: str,
    ):
        """
        Generates a device config using arouteserver

        Arguments:

        - ars_type (`str`): arouteserver type
            (e.g. `bird`, `bird2`)
        - general_config_file (`str`): path to general config file
        - clients_config_file (`str`): path to clients config file
        - output_file (`str`): path to output file
        """

        extra_params = [
            "--use-local-files",
            "logging",
            "--local-files-dir",
            "/srv/bird/etc",
        ]

        # TODO: bird v1 needs to generate
        # separate for each ip version
        #
        # how to store?
        if ars_type == "bird":
            extra_params += ["--ip-ver", "4"]
        elif ars_type == "bird2":
            ars_type = "bird"
            extra_params += ["--target-version", "2.0.10"]

        # no reasonable way found to call an arouteserver
        # python api - so lets just run the command
        self.run_ars_command(
            ars_type,
            general_config_file,
            clients_config_file,
            output_file,
            extra_params=extra_params,
        )

        with open(output_file) as fh:
            title = f"# generated by ixctl-{settings.PACKAGE_VERSION} at {datetime.now().isoformat()}\n"
            self.body = title + fh.read()

    def generate(self):
        """
        Generate the route server config using arouteserver
        """

        routeserver = self.routeserver
        ars_general = routeserver.ars_general
        ars_clients = routeserver.ars_clients

        config_dir = tempfile.mkdtemp(prefix="ixctl_routeserver_config")

        general_config_file = os.path.join(config_dir, "general.yaml")
        clients_config_file = os.path.join(config_dir, "clients.yaml")
        outfile_config = os.path.join(config_dir, "generated-config.txt")
        outfile_md = os.path.join(config_dir, "rs-config-markdown.md")

        with open(general_config_file, "w") as fh:
            as_yaml = yaml.dump(ars_general, Dumper=Dumper)
            self.ars_general = as_yaml
            fh.write(as_yaml)

        with open(clients_config_file, "w") as fh:
            as_yaml = yaml.dump(ars_clients, Dumper=Dumper)
            self.ars_clients = as_yaml
            fh.write(as_yaml)

        # generate device config
        self.generate_config(
            routeserver.ars_type,
            general_config_file,
            clients_config_file,
            outfile_config,
        )

        # generate markdown
        self.generate_markdown(general_config_file, clients_config_file, outfile_md)

        self.save()


@reversion.register()
@grainy_model(
    namespace="net",
    namespace_instance="net.{instance.org.permission_id}.{instance.asn}",
)
class Network(PdbRefModel):

    """
    Describes a network

    Can have a reference to a peeringdb netlan object
    """

    name = models.CharField(max_length=255, blank=False)
    asn = models.IntegerField()
    instance = models.ForeignKey(
        Instance, related_name="net_set", on_delete=models.CASCADE, null=True
    )

    class PdbRef(PdbRefModel.PdbRef):
        pdbctl = pdbctl.Network
        fields = {"asn": "pdb_id"}

    class HandleRef:
        tag = "net"

    class Meta:
        db_table = "ixctl_net"
        verbose_name_plural = _("Networks")
        verbose_name = _("Network")
        unique_together = (("instance", "asn"),)

    @classmethod
    def create_from_pdb(cls, instance, pdb_object, save=True, **fields):
        """
        create instance from peeringdb network

        Argument(s):

        - instance (`Instance`): instance that contains this network
        - pdb_object (`fullctl.service_bridge.pdbctl.Network`): pdb network
        - save (`bool`): if True commit to the database, otherwise dont

        Keyword Argument(s):

        Any arguments passed will be used to set properties on the
        object before creation

        Returns:

        - `Network` instance
        """

        net = super().create_from_pdb(
            pdb_object,
            save=save,
            instance=instance,
            name=pdb_object.name,
            asn=pdb_object.asn,
            **fields,
        )

        return net

    @property
    def display_name(self):
        """
        Will return the exchange name if specified.

        If self.name is not specified and pdb reference is set return
        the name of the peeringdb ix instead

        If peeringdb reference is not specified either, return
        generic "Nameless Exchange ({id})"
        """

        if self.name:
            return self.name
        if self.pdb_id:
            return self.pdb.name
        return f"Unknown Network (AS{self.asn})"

    @property
    def org(self):
        return self.instance.org

    @property
    def members(self):
        if not hasattr(self, "_members"):
            self._members = [
                member for member in InternetExchangeMember.objects.filter(asn=self.asn)
            ]
        return self._members

    def __str__(self):
        return f"{self.name} (AS{self.asn})"


class RouteserverMember(models.Model):
    routeserver = models.ForeignKey(
        Routeserver,
        on_delete=models.CASCADE,
        related_name="ix_members",
    )
    ix_member = models.ForeignKey(
        InternetExchangeMember,
        on_delete=models.CASCADE,
        related_name="routeservers",
    )
    event = ReferencedObjectUUIDField(
        bridge=auditctl.Event,
        null=True,
        blank=False,
        help_text=_("auditCtl event reference"),
    )

    class Meta:
        db_table = "ixctl_rs_members"
        verbose_name = _("Members to Routeservers Relationship")
        verbose_name_plural = _("Members to Routeservers Relationship")
        unique_together = ("ix_member", "routeserver")

    @classmethod
    def preload_events(cls, routeserver_members):
        """
        Preloads auditctl event information

        Argument(s):
        - routeserver_members (`list` of `RouteServerMembers`): routeserver_members to load events for
        """
        event_ids = [
            str(routeserver_member.event)
            for routeserver_member in routeserver_members
            if routeserver_member.event
        ]
        if not event_ids:
            return

        events = auditctl.Event().get_events_by_ids(event_ids=event_ids)
        if not events:
            return

        events = {event.id: event for event in events}
        for routeserver_member in routeserver_members:
            if not routeserver_member.event:
                continue

            event = events.get(str(routeserver_member.event))
            if not event:
                continue

            routeserver_member._event_object = event


@reversion.register
class TrafficAlertConfig(models.Model):
    ix = models.OneToOneField(
        InternetExchange,
        on_delete=models.CASCADE,
        related_name="org_traffic_alert_config_set",
    )

    traffic_level = models.PositiveIntegerField(
        default=90,
        help_text=_("Percentage of available bandwidth."),
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )

    time_period = models.PositiveIntegerField(
        help_text=_("Period after which notifications are potentially sent (minutes)."),
        validators=[
            MinValueValidator(1),
            MaxValueValidator(1440),  # 1440 being 1 day in minutes
        ],
    )

    operator_emails = models.BooleanField(
        default=False,
        help_text=_("Are email alerts to ix operators enabled?"),
    )

    member_emails = models.BooleanField(
        default=False,
        help_text=_("Are email alerts to ix members enabled?"),
    )

    ALLOWED_MAX_EMAIL_FREQUENCY = [(1, "1"), (7, "7"), (30, "30"), (90, "90")]

    operator_emails_max_frequency = models.PositiveIntegerField(
        default=None,
        null=True,
        blank=True,
        help_text=_(
            "Frequency of alert in days (1=daily, 7=weekly, 30=monthly, 90=quarterly)."
        ),
        choices=ALLOWED_MAX_EMAIL_FREQUENCY,
    )

    member_emails_max_frequency = models.PositiveIntegerField(
        default=None,
        null=True,
        blank=True,
        help_text=_(
            "Frequency of alert in days (1=daily, 7=weekly, 30=monthly, 90=quarterly)."
        ),
        choices=ALLOWED_MAX_EMAIL_FREQUENCY,
    )

    class HandleRef:
        tag = "traffic_alert_config"

    class Meta:
        db_table = "ixctl_traffic_alert_config"
        verbose_name = _("Traffic Alert Config for IX")
        verbose_name_plural = _("Traffic Alert Configs for IX")

    def clean(self):
        super().clean()

        if self.operator_emails and not self.operator_emails_max_frequency:
            raise ValidationError(
                {
                    "operator_emails_max_frequency": _(
                        "You must set a frequency for operator emails."
                    )
                }
            )

        if self.member_emails and not self.member_emails_max_frequency:
            raise ValidationError(
                {
                    "member_emails_max_frequency": _(
                        "You must set a frequency for member emails."
                    )
                }
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)


EMAIL_TEMPLATE_TYPES = (
    ("traffic_alert_net", "Traffic Alert Net"),
    ("traffic_alert_ix", "Traffic Alert IX"),
)


@reversion.register
class EmailTemplate(TemplateModel):
    ix = models.ForeignKey(
        InternetExchange,
        on_delete=models.CASCADE,
        related_name="email_template_set",
    )
    type = models.CharField(
        null=False,
        blank=False,
        help_text=_("The type of email template."),
        choices=EMAIL_TEMPLATE_TYPES,
    )

    class Meta:
        db_table = "ixctl_email_template"
        verbose_name = _("Email Template for IX")
        verbose_name_plural = _("Email Templates for IX")
        constraints = [
            models.UniqueConstraint(fields=["ix", "type"], name="unique_ix_type_pair"),
        ]

    class HandleRef:
        tag = "email_template"

    def clean(self):
        super().clean()
        if (
            EmailTemplate.objects.exclude(pk=self.pk)
            .filter(ix=self.ix, type=self.type)
            .exists()
        ):
            raise ValidationError("Template type for that IX already exists.")

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def get_data(self):
        data = super().get_data()
        capacity_alert = self.context.get("capacity_alert", 0)
        downtime = (self.ix.traffic_poll_time // 60) * capacity_alert
        try:
            traffic_alert_config = TrafficAlertConfig.objects.get(ix=self.ix)
        except TrafficAlertConfig.DoesNotExist:
            traffic_alert_config = TrafficAlertConfig(
                ix=self.ix,
                time_period=100,
                operator_emails=True,
                member_emails=True,
                operator_emails_max_frequency=7,
                member_emails_max_frequency=30,
            )
        data.update(
            ix=self.ix,
            downtime=downtime,
            traffic_alert_config=traffic_alert_config,
        )
        return data
