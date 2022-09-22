import reversion
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_grainy.decorators import grainy_model
from fullctl.django.fields.service_bridge.prefixctl import PrefixSet
from fullctl.django.models.abstract.base import HandleRefModel
from fullctl.django.models.abstract.template import TemplateModel
from fullctl.django.models.concrete import Instance
from netfields import CidrAddressField

__all__ = (
    "AccessControlList",
    "Instance",
    "FilterRule",
    "FilterRuleTemplate",
)

SOURCE_TYPES = (
    ("prefix", _("Prefix")),
    ("prefix-set", _("Prefix Set")),
)

DEVICE_TYPES = (("cisco-nexus", _("Cisco Nexus")),)

RULE_ACTIONS = (
    ("permit", _("Permit")),
    ("deny", _("Deny")),
)


RULE_PROTOCOLS = (
    ("tcp", _("TCP")),
    ("udp", _("UDP")),
)


def validate_ports(value):
    ports = value.replace(" - ", "-").split("-")
    if len(ports) > 2:
        raise ValidationError("Currently only supports as single port or a port range")
    ports = [str(int(port)) for port in ports]
    return "-".join(ports) or None


@grainy_model(
    namespace="access_control_list",
    namespace_instance="access_control_list.{instance.instance.org.permission_id}.{instance.id}",
)
@reversion.register
class AccessControlList(HandleRefModel):

    """
    Describes an access control list
    """

    instance = models.ForeignKey(
        Instance,
        related_name="access_control_lists",
        on_delete=models.CASCADE,
        help_text=_("Id of your organization's aclctl instance"),
    )

    name = models.CharField(
        max_length=255, help_text=_("A user friendly name for the list")
    )
    slug = models.SlugField(
        default="list", help_text=_("A unique url-friendly identifier for the list")
    )

    class Meta:
        db_table = "aclctl_access_control_list"
        verbose_name = _("Access Control List")
        verbose_name_plural = _("Access Control Lists")
        unique_together = (("instance", "slug"),)

    class HandleRef:
        tag = "access_control_list"

    @property
    def org(self):
        return self.instance.org


@grainy_model(
    namespace="access_control_list",
    namespace_instance="access_control_list.{instance.access_control_list.org.permission_id}.{instance.id}",
)
@reversion.register
class FilterRule(HandleRefModel):

    """
    Describes a filter rule in an access control list
    """

    access_control_list = models.ForeignKey(
        AccessControlList,
        on_delete=models.CASCADE,
        related_name="filter_rules",
        help_text=_("The filter rule is defined in this access control list"),
    )

    priority = models.IntegerField(
        default=50,
        help_text=_(
            "Ordering priority of the filter rule. When the filter rule configuration is later rendered this will dictate the rule's place in the output"
        ),
    )

    action = models.CharField(max_length=255, choices=RULE_ACTIONS, default="permit")
    protocol = models.CharField(max_length=255, choices=RULE_PROTOCOLS, default="tcp")

    src_port = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        validators=(validate_ports,),
        help_text=_("Source port"),
    )
    src_prefix = CidrAddressField(
        null=True,
        blank=True,
        help_text=_(
            "Source prefix - if src_type is set to `prefix` this property is used for the source prefix. Should be a valid ipv4 or ipv6 prefix"
        ),
    )
    src_prefix_set = PrefixSet(
        null=True,
        blank=True,
        help_text=_(
            "Source prefix set through prefixCtl - if src_type is set to `prefix_set` this property is used for the source prefix(es). Should be the id of one of your prefixCtl prefix sets"
        ),
    )
    src_type = models.CharField(
        max_length=255,
        default="prefix",
        choices=SOURCE_TYPES,
        help_text=_(
            "Determines whether the source prefix comes from the `src_prefix` property or the `src_prefix_set` property"
        ),
    )

    dest_port = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        validators=(validate_ports,),
        help_text=_("Destination port"),
    )
    dest_prefix = CidrAddressField(
        null=True,
        blank=True,
        help_text=_(
            "Destination prefix - if dest_type is set to `prefix` this property is used for the destination prefix. Should be a valid ipv4 or ipv6 prefix"
        ),
    )
    dest_prefix_set = PrefixSet(
        null=True,
        blank=True,
        help_text=_(
            "Destination prefix set through prefixCtl - if dest_type is set to `prefix_set` this property is used for the destination prefix(es). Should be the id of one of your prefixCtl prefix sets"
        ),
    )
    dest_type = models.CharField(
        max_length=255,
        default="prefix",
        choices=SOURCE_TYPES,
        help_text=_(
            "Determines whether the destination prefix comes from the `dest_prefix` property or the `dest_prefix_set` property"
        ),
    )

    # TODO device reference either through devicectl
    # or nautobot

    class Meta:
        db_table = "aclctl_filter_rule"
        verbose_name = _("Traffic filter rule")
        verbose_name_plural = _("Traffic filter rules")

    class HandleRef:
        tag = "filter_rule"

    @classmethod
    def new_rule_priority(cls, access_control_list):

        last = (
            cls.objects.filter(access_control_list=access_control_list)
            .order_by("priority")
            .last()
        )

        if last:
            return last.priority + settings.ACLCTL_PRIORITY_GAP

        return settings.ACLCTL_PRIORITY_GAP

    @property
    def src_prefixes(self):
        if self.src_type == "prefix":
            return [str(self.src_prefix or "")]
        prefix_set = self.src_prefix_set.object
        return [prefix["prefix"] for prefix in prefix_set.prefixes]

    @property
    def dest_prefixes(self):
        if self.dest_type == "prefix":
            return [str(self.dest_prefix or "")]
        prefix_set = self.dest_prefix_set.object
        return [prefix["prefix"] for prefix in prefix_set.prefixes]

    @property
    def src_port_cisco(self):
        if not self.src_port:
            return ""
        port = self.src_port.split("-")
        if len(port) == 1:
            return f"eq {port[0]}"
        return f"range {port[0]} {port[1]}"

    @property
    def dest_port_cisco(self):
        if not self.dest_port:
            return ""
        port = self.dest_port.split("-")
        if len(port) == 1:
            return f"eq {port[0]}"
        return f"range {port[0]} {port[1]}"

    def __str__(self):
        return f"{self.src_prefix}:{self.src_port} / {self.dest_prefix}:{self.dest_port} ({self.id})"


@grainy_model(
    namespace="filter_rule",
    namespace_instance="filter_rule.{instance.instance.org.permission_id}.{instance.id}",
)
@reversion.register
class FilterRuleTemplate(TemplateModel):

    type = models.CharField(
        max_length=255,
        choices=DEVICE_TYPES,
        default="cisco-nexus",
        help_text=_("Device type"),
    )

    instance = models.ForeignKey(
        Instance,
        related_name="filter_rule_templates",
        on_delete=models.CASCADE,
        help_text=_("Id of your organization's aclctl instance"),
    )

    class HandleRef:
        tag = "filter_rule_template"

    class Meta:
        db_table = "aclctl_filter_rule_template"
        verbose_name = _("Traffic filter rule template")
        verbose_name = _("Traffic filter rule templates")
        unique_together = (("instance", "name"),)

    def get_data(self):

        qset = self.context["access_control_list"].filter_rules.all()

        return {
            "filter_rules": list(qset.order_by("priority")),
        }
