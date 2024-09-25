from uuid import UUID

import fullctl.service_bridge.devicectl as devicectl
from django.db.models import Q
from fullctl.django.rest.decorators import grainy_endpoint
from fullctl.django.rest.route.service_bridge import route
from fullctl.django.rest.views.service_bridge import (
    DataViewSet,
    HeartbeatViewSet,
    MethodFilter,
    StatusViewSet,
)
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound
from rest_framework.response import Response

import django_ixctl.models.ixctl as models
from django_ixctl.rest.serializers.service_bridge import Serializers

import structlog
logger = structlog.getLogger("django_structlog")


@route
class Status(StatusViewSet):
    checks = ("bridge_peerctl", "bridge_aaactl", "bridge_pdbctl")


@route
class Heartbeat(HeartbeatViewSet):
    pass


@route
class InternetExchange(DataViewSet):
    path_prefix = "/data"
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("ids", "id__in"),
        ("org", "instance__org__remote_id"),
        ("q", "name__icontains"),
        ("sot", "source_of_truth"),
        ("verified", "verified"),
        ("asns", "member_set__asn_in"),
    ]
    autocomplete = "name"
    allow_unfiltered = True

    queryset = models.InternetExchange.objects.filter(status="ok").select_related(
        "instance", "instance__org"
    )
    serializer_class = Serializers.ix


@route
class InternetExchangePrefix(DataViewSet):
    path_prefix = "/data"
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("ix", "ix_id"),
        ("ix_verified", "ix__verified"),
        ("prefix", "prefix"),
    ]

    join_xl = {"ix": ("ix",)}

    queryset = models.InternetExchangePrefix.objects.filter(status="ok").select_related(
        "ix", "ix__instance", "ix__instance__org"
    )
    serializer_class = Serializers.prefix


@route
class InternetExchangeMember(DataViewSet):
    path_prefix = "/data"
    allowed_http_methods = ["GET", "PATCH"]
    valid_filters = [
        ("ids", "id__in"),
        ("org", "ix__instance__org__remote_id"),
        ("ix", "ix_id"),
        ("ix_verified", "ix__verified"),
        ("asn", "asn"),
        ("asns", "asn__in"),
        ("ports", MethodFilter("ports")),
        ("peers", MethodFilter("peers")),
        ("peers_from_port", MethodFilter("peers_from_port")),
        ("sot", MethodFilter("sot")),
        ("ip", MethodFilter("ip")),
        ("mutual", MethodFilter("mutual")),
        ("q", MethodFilter("search")),
        ("distinct", MethodFilter("distinct")),
    ]

    join_xl = {"ix": ("ix",), "ix_name": ("ix",)}

    queryset = models.InternetExchangeMember.objects.filter(status__in=["ok", "admin_down"]).select_related(
        "ix", "ix__instance", "ix__instance__org"
    )
    serializer_class = Serializers.member

    def filter_peers(self, qset, value):
        member = self.get_queryset().filter(id=value).first()
        return qset.filter(ix_id=member.ix_id, status="ok").exclude(id=value)

    def filter_peers_from_port(self, qset, value):
        class Port:
            def __init__(self, _id) -> None:
                self.id = int(_id)

        member = self.get_queryset().filter(port=Port(value)).first()
        return qset.filter(ix_id=member.ix_id, status__in=["ok", "admin_down"]).exclude(id=member.id)

    def filter_mutual(self, qset, value):
        asn = value
        ix_ids = set()
        ix_qset = self.get_queryset().filter(
            asn=asn, status="ok", ix__source_of_truth=True
        )

        for member in ix_qset:
            ix_ids.add(member.ix_id)

        return qset.filter(ix_id__in=ix_ids).exclude(asn=asn)

    def filter_sot(self, qset, value):
        return qset.filter(ix__source_of_truth=True).exclude(
            ix__pdb_id__isnull=True, ix__pdb_id=0
        )

    def filter_ip(self, qset, value):
        return qset.filter(Q(ipaddr4=value) | Q(ipaddr6=value))

    def filter_ports(self, qset, value):
        port_ids = list(map(int, value.split(",")))
        ids = []
        for member in qset:
            if member.port and int(member.port) in port_ids:
                ids.append(member.id)

        return qset.filter(id__in=ids)

    def filter_search(self, qset, value: str):
        """
        Filters by member ASN or name (network name)
        """
        return qset.filter(Q(asn__startswith=value) | Q(name__icontains=value))

    def filter_distinct(self, qset, value: str):
        """
        Apply distinct filter to queryset for a given field
        """
        return qset.distinct(value)

    @action(
        detail=False,
        methods=["PATCH"],
        url_path="sync/(?P<member_id>[^/.]+)/(?P<member_port>[^/]+)/status",
    )
    @grainy_endpoint(namespace="service_bridge")
    def status(self, request, member_id, member_port, *args, **kwargs):
        """
        Updates the status of a specific member port.

        This method is an API endpoint that handles PATCH requests to update the
        status of a specified member port. The URL pattern expects the `member_id`
        and `member_port` to be included in the URL path.

        Args:
          request (Request): The HTTP request object containing the status data.
          member_id (str): The ID of the member whose port status is being updated.
          member_port (str): The port of the member whose status is being updated.
          *args: Variable length argument list.
          **kwargs: Arbitrary keyword arguments.

        Returns:
          Response: A Response object containing serialized data of the updated
          member instance.

        Raises:
          BadRequest: If the status is not provided in the request data or if
          the member does not exist.

        Example:
          PATCH /sync/<member_id>/<member_port>/status
          {
            "status": "admin_down"
          }
        """

        status = request.data.get("status")

        member = models.InternetExchangeMember.objects.filter(
            ix__verified=True, id=member_id
        ).first()

        models.InternetExchangeMember().set_ports_status(member=member,
                                                         status=status)

        return Response(Serializers.member(instance=member, many=False).data)

    @action(
        detail=False,
        methods=["PUT"],
        url_path="sync/(?P<asn>[^/.]+)/(?P<ip>[^/]+)/mac-address",
    )
    @grainy_endpoint(namespace="service_bridge")
    def mac_address(self, request, asn, ip, *args, **kwargs):
        macaddr_set = request.data.getlist("macaddr_set")
        members = models.InternetExchangeMember.objects.filter(
            ix__verified=True, asn=asn, ipaddr4=ip
        ).prefetch_related("mac_addresses")

        for member in members:
            member.macaddr_set = macaddr_set
        return Response(Serializers.member(instance=members, many=True).data)

    @action(detail=False, methods=["PUT"], url_path="sync/as-macro")
    @grainy_endpoint(namespace="service_bridge")
    def as_macro(self, request, *args, **kwargs):
        as_macro = request.data.get("as_macro")
        asn = request.data.get("asn")

        members = models.InternetExchangeMember.objects.filter(asn=asn)

        members.update(as_macro_override=as_macro)

        return Response(Serializers.member(instance=members, many=True).data)

    @action(
        detail=False,
        methods=["PUT"],
        url_path="sync/(?P<asn>[^/.]+)/(?P<member_ip>[^/]+)/(?P<router_ip>[^/]+)/md5",
    )
    @grainy_endpoint(namespace="service_bridge")
    def md5(self, request, asn, member_ip, router_ip, *args, **kwargs):
        md5 = request.data.get("md5")

        # find route servers at verified internet exchanges that
        # match the provided router ip

        route_servers = models.Routeserver.objects.filter(
            ix__verified=True, router_id=router_ip
        ).select_related("ix")

        members = []

        # update memember md5s using the member ip to identify them

        for rs in route_servers:
            try:
                member = rs.ix.member_set.get(
                    asn=asn, ipaddr4=member_ip, is_rs_peer=True
                )
                member.md5 = md5
                member.save()
                members.append(member)
            except models.InternetExchangeMember.DoesNotExist:
                continue

        return Response(Serializers.member(instance=members, many=True).data)

    @action(detail=True, methods=["GET"])
    @grainy_endpoint(namespace="service_bridge")
    def traffic(self, request, pk=None, *args, **kwargs):
        member = self.get_object()

        if not member.port:
            return Response({})

        virtual_port_id = member.port.object.virtual_port

        start_time = request.query_params.get("start_time")
        duration = request.query_params.get("duration")
        step = request.query_params.get("step")

        return Response(
            devicectl.VirtualPort().traffic(
                virtual_port_id,
                start_time=start_time,
                duration=duration,
                step=step,
                traffic_source=member.ix.graph_traffic_source,
            )
        )

    @action(detail=True, methods=["GET"])
    @grainy_endpoint(namespace="service_bridge")
    def traffic_asn_pair(self, request, pk=None, *args, **kwargs):
        member = self.get_object()

        if not member.port:
            return Response({})

        virtual_port_id = member.port.object.virtual_port

        start_time = request.query_params.get("start_time")
        duration = request.query_params.get("duration")
        step = request.query_params.get("step")
        asn_src = request.query_params.get("asn_src")
        asn_dst = request.query_params.get("asn_dst")

        return Response(
            devicectl.VirtualPort().traffic_asn_pair(
                virtual_port_id,
                asn_src=asn_src,
                asn_dst=asn_dst,
                start_time=start_time,
                duration=duration,
                step=step,
            )
        )

    @action(
        detail=False,
        methods=["PUT"],
        url_path="set-event-reference/(?P<asn>[^/]+)",
    )
    @grainy_endpoint(namespace="service_bridge")
    def set_event_reference(self, request, asn):
        address = request.data.get("address")
        try:
            member = models.InternetExchangeMember.objects.get(
                Q(ipaddr4=address) | Q(ipaddr6=address),
                asn=int(asn),
                is_rs_peer=True,
                ix__verified=True,
            )
        except models.InternetExchangeMember.MultipleObjectsReturned as ex:
            raise NotFound({"non_field_errors": [str(ex)]})
        routeserver = models.Routeserver.objects.get(
            router_id=request.data.get("routeserver_router_id")
        )
        routeserver_member, _ = models.RouteserverMember.objects.get_or_create(
            ix_member=member, routeserver=routeserver
        )
        routeserver_member.event = UUID(request.data.get("event"))
        routeserver_member.save()
        serializer = self.serializer_class(instance=member)
        return Response(serializer.data)

    @action(detail=True, methods=["GET"])
    @grainy_endpoint(namespace="service_bridge")
    def metric(self, request, pk=None, *args, **kwargs):
        member = self.get_object()

        if not member.port:
            return Response({})

        virtual_port_id = member.port.object.virtual_port

        return Response(
            devicectl.VirtualPort().metric(
                virtual_port_id,
            )
        )

    @action(detail=True, methods=["GET"])
    @grainy_endpoint(namespace="service_bridge")
    def metric_table(self, request, pk=None, *args, **kwargs):
        member = self.get_object()

        if not member.port:
            return Response({})

        virtual_port_id = member.port.object.virtual_port

        return Response(
            devicectl.VirtualPort().metric_table(
                virtual_port_id,
            )
        )


@route
class RouteServer(DataViewSet):
    path_prefix = "/data"
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("ix", "ix_id"),
        ("ixs", "ix__in"),
        ("ix_verified", "ix__verified"),
        ("asn", "asn"),
        ("asns", "asn__in"),
        ("peer_asn", MethodFilter("peer_asn")),
        ("sot", MethodFilter("sot")),
        ("ip", "router_id"),
    ]

    join_xl = {"ix": ("ix",)}

    queryset = models.Routeserver.objects.filter(status="ok").select_related(
        "ix", "ix__instance", "ix__instance__org"
    )
    serializer_class = Serializers.routeserver

    def filter_sot(self, qset, value):
        return qset.filter(ix__source_of_truth=True).exclude(
            ix__pdb_id__isnull=True, ix__pdb_id=0
        )

    def filter_peer_asn(self, qset, value):
        return qset.filter(ix__verified=True, ix__member_set__asn=value).distinct("id")

    @action(
        detail=False,
        methods=["PUT"],
        url_path="set-event-reference/(?P<router_id>[^/]+)",
    )
    @grainy_endpoint(namespace="service_bridge")
    def set_event_reference(self, request, router_id):
        routeserver = models.Routeserver.objects.get(router_id=router_id)
        routeserver.event = UUID(request.data.get("event"))
        routeserver.save()
        serializer = self.serializer_class(instance=routeserver)
        return Response(serializer.data)


@route
class RouteserverMember(DataViewSet):
    path_prefix = "/data"
    allowed_http_methods = ["GET"]
    queryset = models.RouteserverMember.objects.all()
    serializer_class = Serializers.routeserver_member
    valid_filters = [
        ("rss", "routeserver__in"),
    ]
