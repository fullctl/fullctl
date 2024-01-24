from datetime import timedelta

import structlog
from django.conf import settings
from django.utils import timezone
from fullctl.django.models.concrete import Organization

import django_auditctl.util as util
from django_auditctl.models.auditctl import Event, Heartbeat
from django_auditctl.schema import ErrorDetails

log = structlog.get_logger("django")

__all__ = [
    "overdue",
    "Heartbeat",
]


def overdue():
    """
    Returns Heartbeat queryset of overdue heartbeats.
    """

    # Get the idle time from settings
    idle_time = settings.HEARTBEAT_EXPECTED_INTERVAL

    log.info("checking for overdue heartbeats", idle_time=idle_time)

    # Get the current time
    current_time = timezone.now()
    offset = current_time - timedelta(seconds=idle_time)

    # Get the heartbeat objects
    return Heartbeat.objects.filter(updated__lte=offset)


def process_overdue():
    """
    Loops through the overdue heartbeats and creates an event for each org
    holding all overdue objects
    """

    object_ids_by_org = {}
    current_time = timezone.now()

    # current time seconds and microseconds
    current_time = current_time.replace(second=0, microsecond=0)

    # first we collect the heartbeat object ids by org

    for heartbeat in overdue():
        id_parts = util.object_id_to_parts(heartbeat.object_id)
        object_ids_by_org.setdefault(id_parts["org_tag"], []).append(
            heartbeat.object_id
        )

    # load orgs by tag

    orgs = {
        org.slug: org
        for org in Organization.objects.filter(slug__in=object_ids_by_org.keys())
    }

    # then we create heartbeat error events for each org
    # at object id v1.0/{org}/heartbeat/{current_time}
    #
    # using current_time as the ref_id allows us to create a single event
    # holding all overdue objects, and also trigger re-notification.

    for org_tag, object_ids in object_ids_by_org.items():
        log.info(
            "checking heartbeat error event", org_tag=org_tag, object_ids=object_ids
        )

        # Initialize a list to collect object_ids due for notification
        objects_due_for_notification = []

        for object_id in object_ids:
            heartbeat = Heartbeat.objects.get(object_id=object_id)
            if (
                not heartbeat.last_notified
                or heartbeat.updated > heartbeat.last_notified
            ):
                # If there's a new heartbeat failure since the last notification, add to the list
                objects_due_for_notification.append(object_id)

                # Update the Heartbeat record with the current time as the last notification time
                heartbeat.last_notified = timezone.now()
                heartbeat.save(update_fields=["last_notified"])

        # If there are object_ids due for notification, create an event
        if objects_due_for_notification:
            event_object_id = util.parts_to_object_id(
                version="v0.1",
                org_tag=org_tag,
                ref_tag="heartbeat",
                ref_id=f"{current_time}",
            )

            Event.objects.create(
                org=orgs[org_tag],
                object_id=event_object_id,
                status="error",
                error=ErrorDetails(
                    message="Heartbeat overdue",
                    components=[
                        {
                            "id": overdue_object_id,
                            "kind": "heartbeat",
                        }
                        for overdue_object_id in object_ids
                    ],
                ).dict(),
            )
