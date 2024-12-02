import structlog
from fullctl.django.rest.mixins import CachedObjectMixin
from fullctl.django.rest.serializers.metric import Serializers as MetricSerializers
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

import django_devicectl.models as models
import django_devicectl.mrtg as mrtg
from django_devicectl.rest.decorators import grainy_endpoint
from django_devicectl.rest.route.devicectl import route
from django_devicectl.rest.serializers.mrtg import Serializers

logger = structlog.get_logger("django_structlog")


@route
class MetricMrtg(CachedObjectMixin, viewsets.GenericViewSet):

    """
    Provides endpoints for querying mrtg data for total ix and port traffic

    MRTG data is currently still inserted / updated via the virtual port /traffic endpoint.
    """

    serializer_class = Serializers.mrtg
    queryset = models.Device.objects.all()
    lookup_url_kwarg = "device_id"
    ref_tag = "metric/mrtg"

    @action(
        detail=False,
        methods=["get"],
        url_path="graph/ix/(?P<ix_id>[^/.]+)",
        serializer_class=MetricSerializers.query_result,
    )
    @grainy_endpoint(namespace="device.{request.org.permission_id}")
    def graph_ix_total(self, request, org, ix_id, *args, **kwargs):

        """
        Aggregate mrtg data to get total traffic for a specific IX

        Will provide 4 metrics:

        - bps_in: Total bits per second in
        - bps_in_max: Maximum bits per second in
        - bps_out: Total bits per second out
        - bps_out_max: Maximum bits per second out

        Query parameters:

        - start: start time for the query (unix timestamp or relative time like -1h)
        - end: end time for the query (unix timestamp or relative time like -1h)
        - step: step size for the query (seconds)
        """
        start = request.query_params.get("start", "-1h")
        end = request.query_params.get("end", None)
        step = request.query_params.get("step", "15m")

        # query mrtg data for device
        data = mrtg.query_graph_ix_total(
            org_id=org.remote_id,
            ix_id=ix_id,
            step=step,
            start=start,
            end=end,
        )
        return Response(data.model_dump())

    @action(
        detail=False,
        methods=["get"],
        url_path="graph/port/(?P<port_id>[^/.]+)",
        serializer_class=MetricSerializers.query_result,
    )
    @grainy_endpoint(namespace="device.{request.org.permission_id}")
    def graph_port_total(self, request, org, port_id, *args, **kwargs):

        """
        Aggregate mrtg data to get total traffic for a specific port

        Will provide 4 metrics:

        - bps_in: Total bits per second in
        - bps_in_max: Maximum bits per second in
        - bps_out: Total bits per second out
        - bps_out_max: Maximum bits per second out

        Query parameters:

        - start: start time for the query (unix timestamp or relative time like -1h)
        - end: end time for the query (unix timestamp or relative time like -1h)
        - step: step size for the query (seconds)
        """

        start = request.query_params.get("start", "-1h")
        end = request.query_params.get("end", None)
        step = request.query_params.get("step", "15m")

        # query mrtg data for device
        data = mrtg.query_graph_port_total(
            org_id=org.remote_id,
            port_id=port_id,
            step=step,
            start=start,
            end=end,
        )
        return Response(data.model_dump())
