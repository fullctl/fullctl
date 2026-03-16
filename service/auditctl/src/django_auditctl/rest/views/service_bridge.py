# from django.db.models import Q
import django_auditctl.models.auditctl as models
from django_auditctl.limit import is_limited, set_limited
from django_auditctl.rest.serializers.service_bridge import Serializers
from rest_framework.decorators import action
from rest_framework.response import Response

from fullctl.django.models import Organization
from fullctl.django.rest.decorators import grainy_endpoint
from fullctl.django.rest.route.service_bridge import route
from fullctl.django.rest.views.service_bridge import (  # DataViewSet,; MethodFilter,
    DataViewSet,
    HeartbeatViewSet,
    StatusViewSet,
)


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

    def _create(self, request, *args, **kwargs):

        object_id = request.data.get("object_id")
        if is_limited(object_id):
            return Response(
                {"error": "rate limit exceeded"},
                status=429,
            )
        set_limited(object_id)

        return super()._create(request, *args, **kwargs)
