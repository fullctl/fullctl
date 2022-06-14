import json
import secrets

import fullctl.django.tasks
import reversion
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_grainy.decorators import grainy_model
from fullctl.django.models.abstract.base import HandleRefModel
from fullctl.django.models.concrete import Instance

from netfields import CidrAddressField

__all__ = (
    "Instance",
    "FilterRule",
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

    src_port = models.PositiveIntegerField()
    dest_port = models.PositiveIntegerField()

    src_prefix = CidrAddressField()
    dest_prefix = CidrAddressField()

    # TODO device reference either through devicectl
    # or nautobot

    class Meta:
        db_table = "aclctl_filter_rule"
        verbose_name = _("Traffic filter rule")
        verbose_name_plural = _("Traffic filter rules")

    class HandleRef:
        tag = "filter_rule"


    def __str__(self):

        return f"{self.src_prefix}:{self.src_port} / {self.dest_prefix}:{self.dest_port} ({self.id})"
