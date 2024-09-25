# from django.db.models import Q
# from fullctl.django.rest.decorators import grainy_endpoint
from fullctl.django.models import Organization
from fullctl.django.rest.route.service_bridge import route
from fullctl.django.rest.views.service_bridge import (  # DataViewSet,; MethodFilter,
    DataViewSet,
    HeartbeatViewSet,
    StatusViewSet,
)

# import django_auditctl.models.auditctl as models
from django_auditctl.rest.serializers.service_bridge import Serializers

# from rest_framework.decorators import action
# from rest_framework.response import Response


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

    def prepare_write_data(self, request):
        data = request.data.copy()
        org_slug = data.get("org")
        if org_slug:
            org = Organization.objects.get(slug=org_slug)
            data["org"] = org.id

        return data
