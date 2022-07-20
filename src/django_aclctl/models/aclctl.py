import json
import secrets

import fullctl.django.tasks
import reversion
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from django_grainy.decorators import grainy_model
from fullctl.django.models.abstract.base import HandleRefModel
from fullctl.django.models.abstract.template import TemplateModel
from fullctl.django.models.concrete import Instance
from fullctl.django.fields.service_bridge.prefixctl import PrefixSet

from netfields import CidrAddressField

__all__ = (
    "Instance",
    "FilterRule",
    "FilterRuleTemplate",
)

SOURCE_TYPES = (
    ("prefix", _("Prefix")),
    ("prefix-set", _("Prefix Set")),
)

DEVICE_TYPES = (
    ("cisco-nexus", _("Cisco Nexus")),
)

RULE_ACTIONS = (

    ("permit", _("Permit")),
    ("deny", _("Deny")),
)


RULE_PROTOCOLS = (
    ("tcp", _("TCP")),
    ("udp", _("UDP")),
)



@grainy_model(namespace="filter_rule", namespace_instance="filter_rule.{instance.instance.org.permission_id}.{instance.id}")
@reversion.register
class FilterRule(HandleRefModel):

    """
    Describes a network traffic filter rule
    """

    instance = models.ForeignKey(
        Instance, related_name="filter_rules", on_delete=models.CASCADE
    )

    priority = models.IntegerField(default=50)

    action = models.CharField(max_length=255, choices=RULE_ACTIONS, default="permit")
    protocol = models.CharField(max_length=255, choices=RULE_PROTOCOLS, default="tcp")

    src_port = models.PositiveIntegerField()
    src_prefix = CidrAddressField(null=True, blank=True)
    src_prefix_set = PrefixSet(null=True, blank=True)
    src_type = models.CharField(max_length=255, default="prefix", choices=SOURCE_TYPES)

    dest_port = models.PositiveIntegerField()
    dest_prefix = CidrAddressField()

    # TODO device reference either through devicectl
    # or nautobot

    class Meta:
        db_table = "aclctl_filter_rule"
        verbose_name = _("Traffic filter rule")
        verbose_name_plural = _("Traffic filter rules")

    class HandleRef:
        tag = "filter_rule"


    @classmethod
    def new_rule_priority(cls, instance):

        last = cls.objects.filter(instance=instance).order_by("priority").last()

        if last:
            return last.priority + settings.ACLCTL_PRIORITY_GAP

        return settings.ACLCTL_PRIORITY_GAP


    @property
    def src_prefixes(self):
        if self.src_type == "prefix":
            return [str(self.src_prefix)]
        prefix_set = self.src_prefix_set.object
        return [prefix["prefix"] for prefix in prefix_set.prefixes]

    def __str__(self):

        return f"{self.src_prefix}:{self.src_port} / {self.dest_prefix}:{self.dest_port} ({self.id})"

@grainy_model(namespace="filter_rule", namespace_instance="filter_rule.{instance.instance.org.permission_id}.{instance.id}")
@reversion.register
class FilterRuleTemplate(TemplateModel):

    type = models.CharField(max_length=255, choices=DEVICE_TYPES, default="cisco-nexus")

    instance = models.ForeignKey(
        Instance, related_name="filter_rule_templates", on_delete=models.CASCADE
    )

    class HandleRef:
        tag = "filter_rule_template"

    class Meta:
        db_table = "aclctl_filter_rule_template"
        verbose_name = _("Traffic filter rule template")
        verbose_name = _("Traffic filter rule templates")
        unique_together = (("instance", "name"),)


    def get_data(self):

        return {
            "filter_rules": list(self.instance.filter_rules.all().order_by("priority")),

        }


