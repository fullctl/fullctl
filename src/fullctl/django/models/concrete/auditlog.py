"""
Models to facilitate auditlogging of actions
"""

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


from fullctl.django.models.concrete.account import Organization


class AuditLog(models.Model):

    """
    timestamp
    """

    created = models.DateTimeField(auto_now=True)
    user = models.ForeignKey(
        get_user_model(), null=True, blank=True, on_delete=models.PROTECT
    )
    key = models.CharField(max_length=8, null=True, blank=True)
    action = models.CharField(max_length=32)
    info = models.CharField(
        max_length=255, help_text=_("Any extra information for the log entry")
    )
    data = models.TextField(
        null=False, default="{}", help_text=_("Any extra data for the log entry")
    )

    # generic foreign key to related object
    object_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="auditlog_object_type_set",
    )
    object_id = models.PositiveIntegerField(null=True, blank=True)
    log_object = GenericForeignKey("object_type", "object_id")

    org_object_type = models.ForeignKey(
        ContentType,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="auditlog_org_object_type_set",
    )
    org_id = models.PositiveIntegerField(null=True, blank=True)
    org = GenericForeignKey("org_object_type", "org_id")
