from fullctl.django.rest.route.service_bridge import route
from fullctl.django.rest.views.service_bridge import HeartbeatViewSet, StatusViewSet


@route
class Status(StatusViewSet):
    checks = ("bridge_aaactl", )


@route
class Heartbeat(HeartbeatViewSet):
    pass
