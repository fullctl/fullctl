from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_grainy.decorators import grainy_model
from fullctl.django.models.abstract.base import HandleRefModel
from fullctl.django.models.concrete import Instance, Organization

import django_auditctl.models.tasks
from django_auditctl.enum import STATUS

__all__ = [
    "Event",
    "Instance",
    "Organization",
]


@grainy_model("audit")
class Event(HandleRefModel):

    """
    Describes an audit event entry

    It defines an object id, a status and a data field
    """

    object_id = models.CharField(max_length=255, help_text=_("Object ID"))
    status = models.CharField(
        max_length=255, choices=STATUS, help_text=_("Status"), default="ok"
    )

    source = models.CharField(
        null=True, blank=True, max_length=255, help_text=_("Source")
    )
    data = models.JSONField(null=True, blank=True, help_text=_("Data"))
    error = models.JSONField(null=True, blank=True, help_text=_("Errors"))

    org = models.ForeignKey(
        Organization,
        related_name="auditctl_entries",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    user = models.ForeignKey(
        get_user_model(),
        related_name="auditctl_entries",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = _("Event")
        verbose_name_plural = _("Events")
        db_table = "auditctl_entry"

        # index object id
        indexes = [models.Index(fields=["object_id"])]

    class HandleRef:
        tag = "event"

    def __str__(self):
        return self.handle

    def __repr__(self):
        return f"<Entry {self.handle}>"
