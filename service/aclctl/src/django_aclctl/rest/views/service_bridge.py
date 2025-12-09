from fullctl.django.rest.route.service_bridge import route
from fullctl.django.rest.views.service_bridge import HeartbeatViewSet, StatusViewSet


@route
class Status(StatusViewSet):

    """
    Returns service bridge status for all the bridges in use by this service
    """

    checks = ("bridge_aaactl",)


@route
class Heartbeat(HeartbeatViewSet):
    """
    Service heart-beat, check if the service is alive and responding
    """
