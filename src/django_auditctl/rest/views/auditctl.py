from fullctl.django.rest.mixins import CachedObjectMixin
from rest_framework import viewsets
from rest_framework.response import Response
from datetime import timedelta
from django.utils import timezone

from django.conf import settings
import django_auditctl.models as models
from django_auditctl.rest.decorators import grainy_endpoint
from django_auditctl.rest.route.auditctl import route
from django_auditctl.rest.serializers.auditctl import Serializers
from django_auditctl.util import parts_to_object_id
from django_auditctl.limit import is_limited, set_limited


def handle_info_status(org, object_id, data):
    """
    Handle the special case when status="info" is sent.
    
    This updates the most recent existing event with the matching object_id
    instead of creating a new event.
    
    Args:
        org: The organization instance
        object_id: The object_id to find the existing event
        data: The incoming data to augment the existing event with
        
    Returns:
        tuple: (success: bool, event: Event or None, error_message: str or None)
    """
    try:
        existing_event_qset = models.Event.objects.filter(
            org=org,
            object_id=object_id
        )
        
        # exclude older than EVENT_MAX_AGE (days)
        existing_event_qset = existing_event_qset.filter(
            created__gte=timezone.now() - timedelta(days=settings.EVENT_MAX_AGE)
        )

        # get the most recent event
        existing_event = existing_event_qset.latest("created")

        # update the event's data using the model method
        existing_event.augment_data(data.get("data", {}))

        return True, existing_event, None
        
    except models.Event.DoesNotExist:
        # If no existing event found, return error
        error_message = f"No existing event found for object_id: {object_id}"
        return False, None, error_message


@route
class Event(CachedObjectMixin, viewsets.GenericViewSet):
    serializer_class = Serializers.event
    queryset = models.Event.objects.all()

    @grainy_endpoint(
        namespace="audit.{request.org.permission_id}",
    )
    def list(self, request, org, instance, *args, **kwargs):
        object_id = parts_to_object_id(
            version=kwargs.get("version"),
            org_tag=kwargs.get("org_tag"),
            ref_tag=kwargs.get("ref_tag"),
            ref_id=kwargs.get("ref_id"),
            delimiter="/",
        )

        queryset = models.Event.filter_events_by_object_id(
            org, object_id, delimiter="/"
        )

        # apply status filters
        status_filters = []

        if request.query_params.get("error", None) == "true":
            status_filters.append("error")
        if request.query_params.get("ok", None) == "true":
            status_filters.append("ok")

        if status_filters:
            queryset = queryset.filter(status__in=status_filters)

        # exclude older than EVENT_MAX_AGE (days)
        queryset = queryset.filter(created__gte=timezone.now() - timedelta(days=settings.EVENT_MAX_AGE))
        
        # apply a limit
        limit = min(int(request.query_params.get("limit", 100)), 1000)

        queryset = queryset[:limit]

        serializer = Serializers.event(
            queryset, many=True, context={"object_id": object_id}
        )
        return Response(serializer.data)

    @grainy_endpoint(
        namespace="audit.{request.org.permission_id}",
    )
    def create(self, request, org, instance, *args, **kwargs):
        object_id = parts_to_object_id(
            version=kwargs.get("version"),
            org_tag=kwargs.get("org_tag"),
            ref_tag=kwargs.get("ref_tag"),
            ref_id=kwargs.get("ref_id"),
        )

        if is_limited(object_id):
            return Response(
                {"error": "rate limit exceeded"},
                status=429,
            )
        set_limited(object_id)

        data = request.data
        data["object_id"] = object_id
        if hasattr(request, "api_key"):
            if hasattr(request.api_key, "user"):
                data["user"] = request.api_key.user.id
            else:
                data["user"] = None
        else:
            data["user"] = request.user.id

        data["org"] = org.id
        
        # Handle special case for status="info"
        if data.get("status") == "info":
            # Find the most recent existing event with matching object_id
            success, event, error_message = handle_info_status(org, object_id, data)
            if success:
                # Return the updated event
                serializer = Serializers.event(
                    event, 
                    context={"object_id": object_id}
                )
                return Response(serializer.data)
            else:
                # If no existing event found, return error
                return Response(
                    {"error": error_message},
                    status=404
                )
        
        serializer = Serializers.event(data=data, context={"object_id": object_id})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
