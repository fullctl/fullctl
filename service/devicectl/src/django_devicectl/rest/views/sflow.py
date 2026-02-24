import base64

import django_devicectl.models as models
import django_devicectl.sflow as sflow
import structlog
from django_devicectl.rest.decorators import grainy_endpoint
from django_devicectl.rest.route.devicectl import route
from django_devicectl.rest.serializers.sflow import Serializers
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

import fullctl.service_bridge.ixctl as ixctl
from fullctl.django.rest.core import BadRequest
from fullctl.django.rest.mixins import CachedObjectMixin
from fullctl.django.rest.serializers.metric import Serializers as MetricSerializers

logger = structlog.get_logger("django_structlog")


@route
class MetricSflow(CachedObjectMixin, viewsets.GenericViewSet):
    """
    Handles datapoint insert and query for sflow data
    for a specific device into the timeseries database

    Also provides endpoints for querying sflow data for total ix, port, asn, and asn pair traffic
    """

    serializer_class = Serializers.sflow_batch
    queryset = models.Device.objects.all()
    lookup_url_kwarg = "device_id"
    ref_tag = "metric/sflow"

    @grainy_endpoint(namespace="sflow_create.{request.org.permission_id}")
    def create(self, request, org, instance, *args, **kwargs):
        """
        Insert sflow data for a specific device

        This is currently gated behind a special `sflow_create` permission.

        While users may read sflow data through their normal `device` permissions,
        they must have the `sflow_create` permission to insert data.
        """

        serializer = self.get_serializer(data=request.data)

        if not serializer.is_valid():
            return BadRequest(serializer.errors)

        serializer.save()

        return Response({"status": "ok"})

    @action(
        detail=False,
        methods=["get"],
        url_path="graph/ix/(?P<ix_id>[^/.]+)",
        serializer_class=MetricSerializers.query_result,
    )
    @grainy_endpoint(namespace="device.{request.org.permission_id}")
    def graph_ix_total(self, request, org, ix_id, *args, **kwargs):
        """
        Aggregate sflow data to get total traffic for a specific IX

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
        start = request.query_params.get("start", "-15m")
        end = request.query_params.get("end", None)
        step = request.query_params.get("step", 300)

        # query sflow data for device
        data = sflow.query_graph_ix_total(
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
        Aggregate sflow data to get total traffic for a specific port

        Will provide 4 metrics:
        - bps_in: Total bits per second in
        - bps_in_max: Maximum bits per second in
        - bps_out: Total bits per second out
        - bps_out_max: Maximum bits per second out

        Query parameters:

        - start: start time for the query (unix timestamp or relative time like -1h)
        - end: end time for the query (unix timestamp or relative time like -1h)
        - step: step size for the query (seconds)
        - query_override: override the query to use a custom query (only superusers)
        """

        start = request.query_params.get("start", "-15m")
        end = request.query_params.get("end", None)
        step = request.query_params.get("step", 300)
        query_override = request.query_params.get("query_override", None)

        # only superusers are allowed to use query_override
        if query_override and not request.user.is_superuser:
            return BadRequest(
                {"error": "Only superusers are allowed to use query_override"}
            )

        # if query override is set decode from base64
        if query_override:
            query_override = base64.b64decode(query_override).decode("utf-8")

        # query sflow data for device
        data = sflow.query_graph_port_total(
            org_id=org.remote_id,
            port_id=port_id,
            step=step,
            start=start,
            end=end,
            query_override=query_override,
        )
        return Response(data.model_dump())

    @action(
        detail=False,
        methods=["get"],
        url_path="graph/port/(?P<port_id>[^/.]+)/asn/(?P<asn>[^/.]+)",
        serializer_class=MetricSerializers.query_result,
    )
    @grainy_endpoint(namespace="device.{request.org.permission_id}")
    def graph_port_asn(self, request, org, port_id, asn, *args, **kwargs):
        """
        Aggregate sflow data to get traffic from the specified ASNs to all other ASNs
        at the specified port

        Will provide 4 metrics per ASN:
        - bps_in: Total bits per second in
        - bps_in_max: Maximum bits per second in
        - bps_out: Total bits per second out
        - bps_out_max: Maximum bits per second out

        Query parameters:

        - start: start time for the query (unix timestamp or relative time like -1h)
        - end: end time for the query (unix timestamp or relative time like -1h)
        - step: step size for the query (seconds)
        """

        start = request.query_params.get("start", "-15m")
        end = request.query_params.get("end", None)
        step = request.query_params.get("step", 300)

        # query sflow data for device
        data = sflow.query_graph_asn(
            org_id=org.remote_id,
            port_id=port_id,
            asn=asn,
            step=step,
            start=start,
            end=end,
        )
        return Response(data.model_dump())

    @action(
        detail=False,
        methods=["get"],
        url_path="graph/port/(?P<port_id>[^/.]+)/asn/(?P<asn_src>[^/.]+)/(?P<asn_dst>[^/.]+)",
        serializer_class=MetricSerializers.query_result,
    )
    @grainy_endpoint(namespace="device.{request.org.permission_id}")
    def graph_port_asn_pair(
        self, request, org, port_id, asn_src, asn_dst, *args, **kwargs
    ):
        """
        Aggregate sflow data to get traffic from the specified ASNs to the other specified ASNs

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

        start = request.query_params.get("start", "-15m")
        end = request.query_params.get("end", None)
        step = request.query_params.get("step", 300)

        # query sflow data for device
        data = sflow.query_graph_asn_pair(
            org_id=org.remote_id,
            port_id=port_id,
            asn_src=asn_src,
            asn_dst=asn_dst,
            step=step,
            start=start,
            end=end,
        )
        return Response(data.model_dump())

    @action(
        detail=False,
        methods=["get"],
        url_path="graph/port/(?P<port_id>[^/.]+)/asn-table",
        serializer_class=Serializers.asn_table_row,
    )
    @grainy_endpoint(namespace="device.{request.org.permission_id}")
    def asn_table(self, request, org, port_id, *args, **kwargs):
        """
        Aggregate sflow data to get traffic from the specified ASNs to all other ASNs
        at the specified port.

        Will provide a table of traffic between ASNs.

        This requires that the specified port exists on a member in IxCtl.

        Query parameters:

        - start: start time for the query (unix timestamp or relative time like -1h)
        - end: end time for the query (unix timestamp or relative time like -1h)
        - step: step size for the query (seconds)
        """

        start = request.query_params.get("start", "-15m")
        end = request.query_params.get("end", None)
        step = request.query_params.get("step", 300)

        virtual_port = models.VirtualPort.objects.get(pk=port_id)
        port = virtual_port.port

        member = ixctl.InternetExchangeMember().first(
            ports=[port.id], org=org.remote_id
        )

        if not member:
            return BadRequest(
                {"error": "No member found with the specified port in IxCtl"}
            )

        members = ixctl.InternetExchangeMember().objects(peers=member.id)

        asn_names = {m.asn: m.name for m in members}

        # query sflow data for device
        data = sflow.asn_table(
            sflow.query_graph_asn(
                org_id=org.remote_id,
                port_id=port_id,
                asn=member.asn,
                step=step,
                start=start,
                end=end,
            ),
            asn_names=asn_names,
        )
        return Response(Serializers.asn_table_row(data, many=True).data)
