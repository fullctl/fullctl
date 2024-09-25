# from django.db.models import Q
from fullctl.django.models import Organization
from fullctl.django.rest.decorators import grainy_endpoint
from fullctl.django.rest.route.service_bridge import route
from fullctl.django.rest.views.service_bridge import (  # DataViewSet,; MethodFilter,
    DataViewSet,
    HeartbeatViewSet,
    StatusViewSet,
)
from rest_framework.decorators import action
from rest_framework.response import Response

import django_auditctl.models.auditctl as models
from django_auditctl.rest.serializers.service_bridge import Serializers


@route
class Status(StatusViewSet):
    checks = ("bridge_peerctl", "bridge_aaactl", "bridge_pdbctl")


@route
class Heartbeat(HeartbeatViewSet):
    pass


@route
class Event(DataViewSet):
    path_prefix = "/data"
    allowed_http_methods = ["POST", "GET"]
    allow_unfiltered = False
    serializer_class = Serializers.event
    queryset = models.Event.objects.all()
    valid_filters = [
        ("ids", "id__in"),
    ]

    def prepare_write_data(self, request):
        data = request.data.copy()
        org_slug = data.get("org")
        if org_slug:
            org = Organization.objects.get(slug=org_slug)
            data["org"] = org.id

        return data

    @action(
        detail=False,
        methods=["GET"],
        url_path="v0.1/(?P<org_slug>[^/]+)/config/liveness",
    )
    @grainy_endpoint(namespace="service_bridge")
    def get_last_updated_config_liveness_event(self, request, org_slug):
        org = Organization.objects.get(slug=org_slug)
        object_id = f"v0.1/{org_slug}/config/liveness"
        event = (
            models.Event.filter_events_by_object_id(org, object_id, delimiter="/")
            .filter(status="ok")
            .first()
        )
        return Response(event.to_dict() if event else {})
