import uuid

from django.contrib.auth import get_user_model
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_grainy.decorators import grainy_model
from fullctl.django.models.abstract.base import HandleRefModel
from fullctl.django.models.concrete import Instance, Organization, Task

from django_auditctl.enum import STATUS

__all__ = [
    "Event",
    "Instance",
    "Organization",
    "OrganizationEmailAlert",
]


@grainy_model("audit")
class Event(HandleRefModel):

    """
    Describes an audit event entry

    It defines an object id, a status and a data field
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

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

    @classmethod
    def filter_events_by_object_id(cls, org, object_id, delimiter="-"):
        """
        Filter Event instances by partial object_id path, matching whole parts only.

        Arguments:
        - partial_path (`str`): partial object_id path to filter by
        - delimiter (`str`, optional): delimiter used in the object_id

        Returns:
        - `QuerySet`: filtered events queryset
        """
        events = Event.objects.filter(org=org)

        # Use Q objects to combine __istartswith and __iexact with an OR operator
        if object_id:
            events = events.filter(
                models.Q(object_id__istartswith=f"{object_id}{delimiter}")
                | models.Q(object_id__iexact=object_id)
            )

        # order by created date
        events = events.order_by("-created")

        return events

    def __str__(self):
        return f"Event({self.id})"

    def __repr__(self):
        return f"Event({self.id})"


@grainy_model("audit")
class EventTask(HandleRefModel):
    """
    Links task instances to audit events
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    event = models.ForeignKey(
        Event,
        related_name="tasks",
        on_delete=models.CASCADE,
    )
    task = models.ForeignKey(
        Task,
        related_name="auditctl_events",
        on_delete=models.CASCADE,
    )

    class Meta:
        verbose_name = _("Event Task")
        verbose_name_plural = _("Event Tasks")
        db_table = "auditctl_event_task"

    class HandleRef:
        tag = "event_task"

    def __str__(self):
        return f"EventTask({self.id})"

    def __repr__(self):
        return f"EventTask({self.id})"


class OrganizationEmailAlert(models.Model):
    """
    Defines an email alert setup for an organization

    TODO: probably should be in fullctl/fullctl - but should
    clarify details first
    """

    org = models.ForeignKey(
        Organization,
        related_name="auditctl_email_alerts",
        on_delete=models.CASCADE,
    )
    email = models.EmailField()

    enabled = models.BooleanField(default=True)

    class Meta:
        verbose_name = _("Organization Email Alert")
        verbose_name_plural = _("Organization Email Alerts")
        db_table = "auditctl_organization_email_alert"

    def __str__(self):
        return f"OrganizationEmailAlert({self.id})"

    def __repr__(self):
        return f"OrganizationEmailAlert({self.id})"


class Heartbeat(HandleRefModel):
    last_notified = models.DateTimeField(
        null=True, blank=True, help_text="Timestamp of the last notification sent"
    )
    """
    Model to track object IDs for heartbeat checks.
    """

    object_id = models.CharField(
        max_length=255,
        unique=True,
        help_text=_("Object ID to perform hearbeat checks for"),
    )

    class Meta:
        db_table = "auditctl_heartbeat"
        verbose_name = _("Heartbeat")
        verbose_name_plural = _("Heartbeats")

    class HandleRef:
        tag = "heartbeat"

    def __str__(self):
        return f"HeartbeatCheck for {self.object_id}"
