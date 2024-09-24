import fullctl.service_bridge.ixctl as ixctl
from fullctl.django.rest.core import BadRequest
from fullctl.django.rest.route.service_bridge import route
from fullctl.django.rest.views.service_bridge import (
    DataViewSet,
    HeartbeatViewSet,
    MethodFilter,
    StatusViewSet,
)
from rest_framework.decorators import action
from rest_framework.response import Response

import django_devicectl.models.devicectl as models
from django_devicectl.rest.serializers.service_bridge import Serializers
from django_devicectl.rest.views.devicectl import PortTrafficMixin

import django_devicectl.mrtg as mrtg
import django_devicectl.sflow as sflow

import structlog
logger = structlog.getLogger('django_structlog')


@route
class Status(StatusViewSet):
    checks = ("bridge_peerctl", "bridge_aaactl", "bridge_pdbctl")


@route
class Heartbeat(HeartbeatViewSet):
    pass


@route
class Facility(DataViewSet):
    path_prefix = "/data"
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("org", "instance__org__remote_id"),
        ("org_slug", "instance__org__slug"),
        ("q", "name__icontains"),
        ("name", "name__iexact"),
        ("ref", "reference"),
    ]
    autocomplete = "name"
    allow_unfiltered = True

    queryset = models.Facility.objects.filter(status="ok")
    serializer_class = Serializers.facility


@route
class Device(DataViewSet):
    path_prefix = "/data"
    allowed_http_methods = ["GET", "POST", "PUT", "DELETE"]
    valid_filters = [
        ("org", "instance__org__remote_id"),
        ("org_slug", "instance__org__slug"),
        ("q", "name__icontains"),
        ("name", "name__iexact"),
        ("ref", "reference"),
        ("port", "physical_ports__logical_port__virtual_ports__port__in"),
        ("facility", "facility_id"),
        ("facility_slug", "facility__slug"),
        ("device", "physical_ports__device_id"),
    ]
    autocomplete = "name"
    allow_unfiltered = True

    queryset = models.Device.objects.filter(status="ok")
    serializer_class = Serializers.device

    def after_create(self, obj, data):
        obj.setup()

        if data.get("facility"):
            obj.facility_id = data.get("facility")
            obj.save()

    @action(
        detail=True,
        methods=["POST"],
        serializer_class=Serializers.device_operational_status,
    )
    def set_operational_status(self, request, pk, *args, **kwargs):
        device = self.get_object()

        data = self.prepare_write_data(request)
        data["device"] = device.id

        # check if DeviceOperationalStatus already exists for device

        try:
            device_operational_status = models.DeviceOperationalStatus.objects.get(
                device=device
            )
        except models.DeviceOperationalStatus.DoesNotExist:
            device_operational_status = None

        slz = Serializers.device_operational_status(
            instance=device_operational_status, data=data
        )
        slz.is_valid(raise_exception=True)
        instance = slz.save()

        models.DeviceConfigHistory.objects.create(
            device=instance.device,
            status=instance.status,
            error_message=instance.error_message,
            event=instance.event,
            url_current=instance.url_current,
            url_reference=instance.url_reference,
            config_current=instance.config_current,
            config_reference=instance.config_reference,
        )

        return Response(slz.data)

    @action(
        detail=True,
        methods=["POST"],
        serializer_class=Serializers.device_referee_report,
    )
    def push_referee_report(self, request, pk, *args, **kwargs):
        device = self.get_object()
        data = self.prepare_write_data(request)
        data["device"] = device.id
        slz = Serializers.device_referee_report(data=data)
        slz.is_valid(raise_exception=True)
        instance = slz.save()
        return Response(Serializers.device_referee_report(instance).data)


@route
class Port(DataViewSet):
    path_prefix = "/data"
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("ids", "id__in"),
        ("org", "virtual_port__logical_port__instance__org__remote_id"),
        ("org_slug", "virtual_port__logical_port__instance__org__slug"),
        ("device", "virtual_port__logical_port__physical_ports__device_id"),
        ("devices", "virtual_port__logical_port__physical_ports__device_id__in"),
        ("ip", MethodFilter("ip")),
        ("has_ips", MethodFilter("has_ips")),
        ("q", MethodFilter("autocomplete")),
    ]
    allow_unfiltered = True

    queryset = models.Port.objects.filter(status="ok")
    serializer_class = Serializers.port

    join_xl = {
        "device": [],
        "physical_ports": [],
    }

    def filter(self, qset, request):
        qset = super().filter(qset, request)
        qset = qset.select_related(
            "virtual_port", "virtual_port__logical_port", "port_info"
        )
        qset = qset.prefetch_related(
            "port_info__ips", "virtual_port__logical_port__physical_ports"
        )

        return qset

    def filter_ip(self, qset, value):
        return qset.filter(port_info__ips__address__host=value)

    def filter_has_ips(self, qset, value):
        return qset.filter(port_info__ips__isnull=False).distinct("pk")

    def filter_autocomplete(self, qset, value):
        return models.Port.search(value, qset).distinct("pk")

    @action(
        detail=False, methods=["POST"], serializer_class=Serializers.request_dummy_ports
    )
    def request_dummy_ports(self, request, *args, **kwargs):
        data = self.prepare_write_data(request)

        serializer = self.serializer_class(data=data)
        if not serializer.is_valid():
            logger.error(f"{serializer.errors=}")
            return BadRequest(f"{serializer.errors=}")

        try:
            ports = serializer.save()
        except Exception as exception:
            logger.error(f"{exception=}")
            return BadRequest(f"request_dummy_port(): {exception=}")

        return Response(Serializers.port(ports, many=True).data)


@route
class Portinfo(DataViewSet):
    path_prefix = "/data"
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("org", "instance__org__remote_id"),
    ]
    allow_unfiltered = True

    queryset = models.PortInfo.objects.filter(status="ok")
    serializer_class = Serializers.port_info


@route
class VirtualPort(PortTrafficMixin, DataViewSet):
    path_prefix = "/data"
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("ref", "reference"),
        ("org", "port__port_info__instance__org__remote_id"),
    ]
    allow_unfiltered = True

    queryset = models.VirtualPort.objects.filter(status="ok")
    serializer_class = Serializers.virtual_port

    def prepare_write_data(self, request):
        data = super().prepare_write_data(request)

        if request.method.lower() == "post" and "logical_port" not in data:
            device = models.Device.objects.get(id=data.get("device"))
            data["logical_port"] = device.logical_ports.first().id

            data["port"] = models.Port.objects.create
            if "vlan_id" not in data:
                data["vlan_id"] = 0

        return data

    @action(detail=True, methods=["GET"], serializer_class=Serializers.port_traffic)
    def traffic(self, request, pk, *args, **kwargs):
        """
        Returns current traffic data for the virtual port
        """

        start_time = request.GET.get("start_time")
        duration = request.GET.get("duration")
        step = request.GET.get("step")

        # traffic source
        # will be one of
        # - rrd_mrtg
        # - vm_mrtg
        # - vm_sflow
        traffic_source = request.GET.get("traffic_source")


        virtual_port = self.get_queryset().get(id=pk)
        data = {}

        if traffic_source == "rrd_mrtg":
            # LEGACY MRTG from RRD
            return self._get_traffic(
                self.get_queryset().get(id=pk),
                start_time=start_time,
                duration=duration,
            )
        elif traffic_source == "vm_mrtg":
            # VICTORIAMETRICS MRTG
            data = mrtg.query_graph_port_total(
                org_id=virtual_port.org.remote_id, port_id=pk, step=step, start=start_time, end=None
            ).model_dump()
        elif traffic_source == "vm_sflow":
            # VICTORIAMETRICS SFLOW
            data = sflow.query_graph_port_total(
                org_id=virtual_port.org.remote_id, port_id=pk, step=step, start=start_time, end=None
            ).model_dump()

        return Response(data)

    @action(detail=True, methods=["get"], url_path="traffic/asn/(?P<asn_src>[^/.]+)/(?P<asn_dst>[^/.]+)")
    def traffic_asn_pair(self, request, pk, asn_src, asn_dst, *args, **kwargs):

        """
        Query sflow data for a specific asn pair
        """

        virtual_port = self.get_queryset().get(id=pk)
        data = {}

        start = request.query_params.get("start_time", "-1h")
        end = request.query_params.get("end", None)
        step = request.query_params.get("step", "15m")

        # query sflow data for device
        data = sflow.query_graph_asn_pair(
            org_id=virtual_port.org.remote_id,
            port_id=virtual_port.id,
            asn_src=asn_src,
            asn_dst=asn_dst,
            step=step,
            start=start,
            end=end,
        )
        return Response(data.model_dump())

    @action(detail=True, methods=["get"], url_path="traffic/asn-table")
    def traffic_asn_table(self, request, pk, *args, **kwargs):

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

        virtual_port = self.get_queryset().get(id=pk)
        data = {}

        start = request.query_params.get("start_time") or request.query_params.get("start", "-15m")
        end = request.query_params.get("end", None)
        step = request.query_params.get("step", 300)

        port = virtual_port.port

        member = ixctl.InternetExchangeMember().first(ports=[port.id], org=virtual_port.org.remote_id)

        if not member:
            return BadRequest({"error": "No member found with the specified port in IxCtl"})

        members = ixctl.InternetExchangeMember().objects(peers=member.id)
        asn_names = {m.asn: m.name for m in members}

        # query sflow data for device
        data = sflow.asn_table(
            sflow.query_graph_asn(
                org_id=virtual_port.org.remote_id,
                port_id=virtual_port.id,
                asn=member.asn,
                step=step,
                start=start,
                end=end,
            ),
            asn_names=asn_names
        )
        return Response(data)

    @action(detail=True, methods=["get"], url_path="metric")
    def metric(self, request, pk, *args, **kwargs):
        """
        Returns current metric data for the virtual port
        """
        virtual_port = self.get_queryset().get(id=pk)

        ports = Serializers.physical_port(
            virtual_port.physical_ports.all(), many=True
        ).data

        return Response(ports)

    @action(detail=True, methods=["get"], url_path="metric_table")
    def metric_table(self, request, pk, *args, **kwargs):
        """
        Returns current metric data for the virtual port
        """
        result = []
        virtual_port = self.get_queryset().get(id=pk)

        ports = Serializers.physical_port(
            virtual_port.physical_ports.all(), many=True
        ).data

        for port in ports:
            flat_data = port.get("metric")
            kv = [
                {"device": port.get("device_name"), "resource": x, "value": y}
                for x, y in flat_data.items()
            ]

            result.extend(kv)

        return Response(result)


@route
class IPAddress(DataViewSet):
    path_prefix = "/data"
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("ref", "reference"),
        ("address", "address"),
        ("org", "instance__org__remote_id"),
    ]
    allow_unfiltered = True

    queryset = models.IPAddress.objects.filter(status="ok")
    serializer_class = Serializers.ip

    def after_create(self, obj, data):
        if data.get("is_management"):
            obj.device.set_management_ip_address(obj.address)

    def after_update(self, obj, data):
        if data.get("is_management"):
            obj.device.set_management_ip_address(obj.address)

    def prepare_write_data(self, request):
        data = super().prepare_write_data(request)

        if "port_info" not in data:
            virtual_port = models.VirtualPort.objects.get(id=data.get("virtual_port"))
            virtual_port.setup()
            port_info = virtual_port.port.port_info
            data["port_info"] = port_info.id

        return data
