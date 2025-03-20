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
import django_devicectl.models.metric_tasks as metric_tasks
from fullctl.django.models.concrete.tasks import TaskLimitError

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

    @action(
        detail=False,
        methods=["post"],
        url_path="write/switch_to_switch",
        serializer_class=Serializers.mrtg_switch_to_switch,
    )
    @grainy_endpoint(namespace="device.{request.org.permission_id}")
    def write_switch_to_switch(self, request, org, *args, **kwargs):
        """
        Write switch to switch data points to the metrics database

        Data points should be in the following format:

        [
            {
                "side_a_name": "device_name",
                "side_b_name": "device_name",
                "bps_out": 1234,
                "timestamp": 1234567890
            }
        ]
        """
        serializer = Serializers.mrtg_switch_to_switch(
            data=request.data, context={"org": org}, many=True
        )
        serializer.is_valid(raise_exception=True)

        # write data to metrics database
        try:
            metric_tasks.InsertMetric.create_task(
                org=org,
                data=serializer.validated_data
            )
        except TaskLimitError as e:
            logger.error("Task limit error", error=e)
            return Response({"error": "Too many insert metric tasks, please wait for some to finish before adding more."}, status=429)

        return Response(serializer.data, status=201)
