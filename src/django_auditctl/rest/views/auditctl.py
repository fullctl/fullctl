from fullctl.django.rest.mixins import CachedObjectMixin
from rest_framework import viewsets
from rest_framework.response import Response

import django_auditctl.models as models
from django_auditctl.rest.decorators import grainy_endpoint
from django_auditctl.rest.route.auditctl import route
from django_auditctl.rest.serializers.auditctl import Serializers
from django_auditctl.util import parts_to_object_id


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
        serializer = Serializers.event(data=data, context={"object_id": object_id})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
