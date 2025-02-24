import ipaddress
import os
from datetime import datetime

import fullctl.service_bridge.aaactl as aaactl
import fullctl.service_bridge.auditctl as auditctl
import fullctl.service_bridge.devicectl as devicectl
import fullctl.service_bridge.pdbctl as pdbctl
import structlog
from django.conf import settings
from django_filters.rest_framework import DjangoFilterBackend
from fullctl.django.auditlog import auditlog
from fullctl.django.models.concrete.tasks import Task
from fullctl.django.rest.api_schema import PeeringDBImportSchema
from fullctl.django.rest.core import BadRequest
from fullctl.django.rest.decorators import load_object
from fullctl.django.rest.filters import CaseInsensitiveOrderingFilter
from fullctl.django.rest.mixins import (
    AuditCtlActionLogMixin,
    CachedObjectMixin,
    OrgQuerysetMixin,
)
from fullctl.django.rest.renderers import PlainTextRenderer
from fullctl.django.tasks import specify_task
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

import django_ixctl.models as models
import django_ixctl.models.port_automation_tasks as port_automation_tasks
import django_ixctl.rest.filters as filters
from django_ixctl.rest.decorators import grainy_endpoint
from django_ixctl.rest.route.ixctl import route
from django_ixctl.rest.serializers.ixctl import OperationalStatusSerializer, Serializers

logger = structlog.getLogger("django_structlog")


class IxOrgQuerysetMixin:
    """
    For objects with URLs that require a "ix_tag" and "org_tag", this filters
    the resulting queryset by matching the org slug and ix slug to the url
    tags.

    Set the 'ix_lookup_field' attribute on the Viewset if the model for the viewset
    does not have an IX attribute, but has a related object with a IX attribute.

    E.g., RouteserverConfig.rs.ix
    """

    def get_queryset(self):
        org_tag = self.kwargs["org_tag"]
        ix_tag = self.kwargs["ix_tag"]
        ix_lookup_field = getattr(self, "ix_lookup_field", "ix")

        filters = {
            f"{ix_lookup_field}__slug": ix_tag,
            f"{ix_lookup_field}__instance__org__slug": org_tag,
        }

        return self.queryset.filter(**filters)


@route
class InternetExchange(CachedObjectMixin, OrgQuerysetMixin, viewsets.GenericViewSet):
    """
    retrieve:
        Return a internet exchange instance.

    list:
        Return all internet exchanges.

    create:
        Create a new internet exchange.

    import_peeringdb:
        Import an internet exhange from Peeringdb.

    update:
        Update an intenet exchange.
    """

    serializer_class = Serializers.ix
    queryset = models.InternetExchange.objects.all()
    ref_tag = "ix"
    lookup_url_kwarg = "ix_tag"
    lookup_field = "slug"

    @grainy_endpoint(namespace="ix.{request.org.permission_id}")
    def list(self, request, org, instance, *args, **kwargs):
        serializer = Serializers.ix(
            instance=models.InternetExchange.objects.filter(instance=instance),
            many=True,
            context={"org": org},
        )
        return Response(serializer.data)

    @auditlog()
    @grainy_endpoint(namespace="ix.{request.org.permission_id}")
    def create(self, request, org, instance, auditlog=None, *args, **kwargs):
        data = request.data
        data["pdb_id"] = None
        data["instance"] = instance.id
        serializer = Serializers.ix(data=data, context={"org": org})
        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        ix = serializer.save()

        return Response(Serializers.ix(instance=ix, context={"org": org}).data)

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @grainy_endpoint(namespace="ix.{request.org.permission_id}.{ix.pk}")
    def retrieve(self, request, org, ix, instance, *args, **kwargs):
        serializer = Serializers.ix(instance=ix, many=False, context={"org": org})
        return Response(serializer.data)

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @auditlog()
    @grainy_endpoint(namespace="ix.{request.org.permission_id}.{ix.pk}")
    def update(self, request, org, ix, instance, auditlog=None, *args, **kwargs):
        data = request.data

        data["instance"] = instance.id

        serializer = Serializers.ix(ix, data=request.data, context={"org": org})

        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        ix = serializer.save()
        ix.instance = instance
        ix.save()

        return Response(Serializers.ix(instance=ix, context={"org": org}).data)

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @auditlog()
    @grainy_endpoint(namespace="ix.{request.org.permission_id}.{ix.pk}")
    def destroy(self, request, org, ix, instance, auditlog=None, *args, **kwargs):
        ix.delete()
        ix.id = request.data.get("id")
        return Response(Serializers.ix(instance=ix, context={"org": org}).data)

    @action(detail=True, methods=["PUT"], serializer_class=Serializers.update_lan)
    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @auditlog()
    @grainy_endpoint(namespace="ix.{request.org.permission_id}")
    def update_lan(self, request, org, instance, ix, *args, **kwargs):
        """
        Updates the LAN properties of the ix

        - mtu
        - vlan id
        """

        serializer = Serializers.update_lan(
            instance=ix,
            data=request.data,
        )
        if not serializer.is_valid():
            return BadRequest(serializer.errors)

        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["POST"], schema=PeeringDBImportSchema())
    @auditlog()
    @grainy_endpoint(namespace="ix.{request.org.permission_id}")
    def import_peeringdb(self, request, org, instance, auditlog=None, *args, **kwargs):
        serializer = Serializers.impix(
            data=request.data,
            context={"instance": instance},
        )

        if not serializer.is_valid():
            return BadRequest(serializer.errors)

        ix = serializer.save()

        auditlog.log("ix:import", log_object=ix, **request.data)

        return Response(Serializers.ix(instance=ix, context={"org": org}).data)

    @action(detail=True, methods=["POST"], serializer_class=Serializers.default_ix)
    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @auditlog()
    @grainy_endpoint(namespace="ix.{request.org.permission_id}")
    def set_as_default(self, request, org, instance, ix, *args, **kwargs):
        """
        Set the exchange as the default exchange for the organization
        """

        serializer = Serializers.default_ix(
            instance=models.OrganizationDefaultExchange.objects.filter(org=org).first(),
            data={"ix": ix.id, "org": org.id},
            context={"instance": instance},
        )

        if not serializer.is_valid():
            return BadRequest(serializer.errors)

        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=["GET"])
    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @grainy_endpoint(namespace="ix.{request.org.permission_id}")
    def devices(self, request, org, instance, ix, *args, **kwargs):
        """
        Retrieve all devices for the exchange based on the linked
        facilities in ix.config["facilities] which is a comma separated list
        of devicectl facility slugs.
        """

        if not ix.facilities:
            return Response([])

        devices = devicectl.Device().objects(
            facility_slugs=ix.facilities, org_slug=org.slug
        )

        # sort by device name
        devices = sorted(devices, key=lambda x: x.name)

        serializer = Serializers.device(
            instance=devices,
            many=True,
        )

        return Response(serializer.data)


@route
class Prefix(CachedObjectMixin, IxOrgQuerysetMixin, viewsets.GenericViewSet):
    serializer_class = Serializers.prefix
    queryset = models.InternetExchangePrefix.objects.all()
    ref_tag = "prefix"
    ix_tag_needed = True
    lookup_url_kwarg = "prefix_id"
    lookup_field = "id"

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @grainy_endpoint(namespace="ix.{request.org.permission_id}.{ix.pk}.prefix")
    def list(self, request, org, instance, ix, *args, **kwargs):
        queryset = self.get_queryset().select_related("ix")
        serializer = Serializers.prefix(
            instance=queryset,
            many=True,
        )
        return Response(serializer.data)

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @auditlog()
    @grainy_endpoint(namespace="ix.{request.org.permission_id}.{ix.pk}.prefix")
    def create(self, request, org, instance, ix, *args, **kwargs):
        data = request.data
        data["ix"] = ix.id
        serializer = Serializers.prefix(data=data, context={"instance": instance})
        if not serializer.is_valid():
            return BadRequest(
                serializer.errors,
                error_map={"unique": "This prefix already exists in this exchange."},
            )

        prefix = serializer.save()

        return Response(Serializers.prefix(instance=prefix).data)

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @load_object("prefix", models.InternetExchangePrefix, ix="ix", id="prefix_id")
    @auditlog()
    @grainy_endpoint(namespace="ix.{request.org.permission_id}.{ix.pk}.prefix")
    def destroy(self, request, org, instance, ix, prefix, *args, **kwargs):
        r = Response(Serializers.prefix(instance=prefix).data)
        prefix.delete()
        return r


@route
class Member(
    AuditCtlActionLogMixin,
    CachedObjectMixin,
    IxOrgQuerysetMixin,
    viewsets.GenericViewSet,
):
    """
    list:
        Return all member instances.

    create:
        Create a new member.

    update:
        Update a member.

    delete:
        Delete a member.
    """

    serializer_class = Serializers.member
    ref_tag = "member"
    queryset = models.InternetExchangeMember.objects.all()
    lookup_url_kwarg = "member_id"
    lookup_field = "id"
    ix_tag_needed = True
    filter_backends = (DjangoFilterBackend,)
    filterset_class = filters.InternetExchangeMemberFilter

    def auditctl_log_append_path(self, request, action: str, **kwargs) -> list[str]:
        """
        Append the path to the auditctl log
        """

        path = []

        if action in ["update", "destroy"]:
            member = self.get_object()
            path = [
                str(member.asn),
                str(member.ipaddr4),
            ]
        elif action == "create":
            path = [
                request.data.get("asn"),
                request.data.get("ipaddr4"),
            ]

        if settings.MEMBER_CASE_NUMBERS_ENABLED:
            case_number = request.data.get("case_number", "")
            if case_number:
                path.append(str(case_number))

        return path

    @action(
        detail=False,
        methods=["POST"],
        serializer_class=Serializers.member_validation_request,
        url_path="validate/case-number",
    )
    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @grainy_endpoint(
        namespace="member.{request.org.permission_id}.{ix.pk}",
    )
    def validate_case_number(self, request, org, instance, ix, *args, **kwargs):
        """
        Start a generic validation task for the supplied case number
        and member data.

        Other plugins can listen for this task and perform additional
        validation steps.
        """

        serializer = Serializers.member_validation_request(
            data=request.data, context={"ix": ix}
        )
        if not serializer.is_valid():
            return BadRequest(serializer.errors)

        task = port_automation_tasks.VerifyCaseNumber.create_task(
            org=org,
            ix_id=ix.id,
            member_data=request.data,
        )

        response_serializer = Serializers.member_validation_result(instance=task)
        return Response(response_serializer.data)

    @action(
        detail=False,
        methods=["POST"],
        serializer_class=Serializers.member_validation_request,
        url_path="validate/request-ip-address-pair",
    )
    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @grainy_endpoint(
        namespace="member.{request.org.permission_id}.{ix.pk}",
    )
    def validate_request_ip_address_pair(
        self, request, org, instance, ix, *args, **kwargs
    ):
        """
        Start a generic validation task that attempts to get the next available
        IP address pair for the member.

        Other plugins can listen for this task and perform the necessary
        operations to get the next available IP address pair.

        This does nothing by default and is meant to be extended by other plugins.
        """

        serializer = Serializers.member_validation_request(
            data=request.data, context={"ix": ix}
        )
        if not serializer.is_valid():
            return BadRequest(serializer.errors)

        task = port_automation_tasks.GetNextAvailableIPAddresses.create_task(
            org=org,
            ix_id=ix.id,
            member_data=request.data,
        )

        response_serializer = Serializers.member_validation_result(instance=task)
        return Response(response_serializer.data)

    @action(
        detail=False,
        methods=["GET"],
        url_path="validate/result/(?P<task_id>[^/]+)",
        serializer_class=Serializers.member_validation_result,
    )
    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @grainy_endpoint(
        namespace="member.{request.org.permission_id}.{ix.pk}",
    )
    def check_validation_result(
        self, request, org, instance, ix, task_id, *args, **kwargs
    ):
        task = Task.objects.get(id=task_id)
        task = specify_task(task)
        if task.org != org:
            return BadRequest({"error": "Task not found"})

        response_serializer = Serializers.member_validation_result(instance=task)
        return Response(response_serializer.data)

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @grainy_endpoint(
        namespace="member.{request.org.permission_id}.{ix.pk}.?",
        handlers={"*": {"key": lambda row, idx: row["asn"]}},
    )
    def list(self, request, org, instance, ix, *args, **kwargs):
        queryset = self.get_members_queryset(request)
        queryset = queryset.prefetch_related("mac_addresses")

        # preload_networks returns a generator, but we need to be able
        # to iterate over it multiple times, so we convert it to a list
        members = list(models.InternetExchangeMember.preload_networks(queryset))
        serializer = Serializers.member(
            instance=members, many=True, context={"instance": instance}
        )
        return Response(serializer.data)

    def get_members_queryset(self, request):
        ordering_filter = CaseInsensitiveOrderingFilter(
            ["name", "asn", "ipaddr4", "ipaddr6", "speed"]
        )
        queryset = self.get_queryset().select_related("ix", "ix__instance")
        queryset = ordering_filter.filter_queryset(request, queryset, self)
        return filters.InternetExchangeMemberFilter(request.GET, queryset=queryset).qs

    @action(detail=False, methods=["GET"], url_path="(?P<pk>[^/.]+)/get-stats")
    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @grainy_endpoint(
        namespace="member.{request.org.permission_id}.{ix.pk}.?",
        handlers={"*": {"key": lambda row, idx: row["asn"]}},
    )
    def get_member_stats(self, request, org, instance, ix, pk, *args, **kwargs):
        member = models.InternetExchangeMember.objects.get(id=pk)
        models.InternetExchangeMember.preload_ports(org, [member])

        bgp_stats, device_metrics = self.get_stats_data(members=[member])
        member_traffic_alert_data_map = self.get_members_traffic_alert_data(
            members=[member]
        )

        data = {
            "member_id": member.id,
            "bgp_stat": bgp_stats,
            "device_metrics": device_metrics,
            "traffic_alert_data": member_traffic_alert_data_map.get(member.id),
        }
        serializer = Serializers.member_stat(instance=data)
        return Response(serializer.data)

    def get_stats_data(self, members):
        physical_ports = set()
        for member in members:
            physical_ports.update(member.physical_ports)

        physical_port_stats = devicectl.PhysicalPortStats().get_physical_port_stats(
            list(physical_ports)
        )

        bgp_stats = {}
        device_metrics = None
        for physical_port in physical_ports:
            if physical_port not in physical_port_stats:
                continue
            json_dict = physical_port_stats.get(physical_port).json_dict
            data = json_dict.get("bgp_stats")
            if data:
                bgp_stats[data[0].get("routeserver_router_id")] = data
            device_metrics = json_dict.get("device_metrics")

        return bgp_stats, device_metrics

    def get_members_traffic_alert_data(self, members):
        try:
            traffic_alert_config = models.TrafficAlertConfig.objects.get(
                ix=members[0].ix
            )
        except models.TrafficAlertConfig.DoesNotExist:
            return {member.id: None for member in members}
        return {
            member.id: {
                "traffic_level": traffic_alert_config.traffic_level,
                "capacity_alert": member.port._object.capacity_alert,
                "traffic_poll_time": member.ix.traffic_poll_time,
                "at_capacity": member.port._object.at_capacity,
                "time_period": traffic_alert_config.time_period,
            }
            if member.port._object
            else None
            for member in members
            if member.port
        }

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @auditlog()
    @grainy_endpoint(
        namespace="member.{request.org.permission_id}.{ix.pk}.?",
        handlers={"*": {"key": lambda row, idx: row["asn"]}},
    )
    def create(self, request, org, instance, ix, *args, **kwargs):
        # retrieve max. memmbers count according
        # to active ixctl plan for org

        max_members = aaactl.OrganizationProduct().get_product_property(
            "ixctl", org.slug, "members", component_object_id=ix.id
        )

        num_members = ix.member_set.all().count()

        if max_members is not None and num_members + 1 > max_members:
            return BadRequest(
                {
                    "non_field_errors": [
                        f"You have reached the limit of allowed networks ({max_members}). "
                        "Please upgrade your ixCtl subscription to add additional networks."
                        f"You can contact us at {settings.SUPPORT_EMAIL} for further information"
                    ]
                }
            )

        data = request.data
        data["ix"] = models.InternetExchange.objects.get(instance=instance, id=ix.pk).id

        serializer = Serializers.member(data=data, context={"instance": instance})

        if not serializer.is_valid():
            return BadRequest(serializer.errors)

        member = serializer.save()

        return Response(Serializers.member(instance=member).data)

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @load_object("member", models.InternetExchangeMember, ix="ix", id="member_id")
    @auditlog()
    @grainy_endpoint(
        namespace="member.{request.org.permission_id}.{ix.pk}.{member.asn}.?",
    )
    def update(self, request, org, instance, ix, member, *args, **kwargs):
        # preload ports
        models.InternetExchangeMember.preload_ports(org, [member])

        serializer = Serializers.member(
            member, data=request.data, context={"instance": instance}
        )

        if not serializer.is_valid():
            return BadRequest(serializer.errors)

        member = serializer.save()

        serializer.instance = member
        response = Response(serializer.data)

        return response

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @load_object("member", models.InternetExchangeMember, ix="ix", id="member_id")
    @auditlog()
    @grainy_endpoint(
        namespace="member.{request.org.permission_id}.{ix.pk}.{member.asn}",
    )
    def destroy(self, request, org, instance, ix, member, *args, **kwargs):
        member_data = Serializers.member(instance=member).data
        r = Response(member_data)

        # if member.port is set we need to unassign it in deviceCtl
        if member.port:
            # at this point we need to mark the physical ports as available
            # in the various backends
            if port_automation_tasks.MemberDeletionFinalize.org_has_services(org):
                port_automation_tasks.MemberDeletionFinalize.create_task(
                    org=org,
                    ix_id=ix.id,
                    member_data=member_data,
                )

        member.delete()
        return r

    @action(detail=False, methods=["GET"])
    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @grainy_endpoint(
        namespace="member.{request.org.permission_id}.{ix.pk}",
    )
    def details(self, request, org, instance, ix, *args, **kwargs):
        queryset = self.get_queryset().select_related("ix", "ix__instance")
        members = list(models.InternetExchangeMember.preload_networks(queryset))

        models.InternetExchangeMember.preload_ports(org, members)

        serializer = Serializers.member_detail(
            instance=members, many=True, context={"instance": instance}
        )

        return Response(serializer.data)

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @load_object("member", models.InternetExchangeMember, ix="ix", id="member_id")
    @grainy_endpoint(
        namespace="member.{request.org.permission_id}.{ix.pk}",
    )
    def retrieve(self, request, org, instance, ix, member_id, member, *args, **kwargs):
        serializer = Serializers.member_detail(
            instance=member, context={"instance": instance}
        )

        models.InternetExchangeMember.preload_ports(org, [member])
        member_data = serializer.data
        member_data["bgp_stat"], _ = self.get_stats_data(members=[member])
        return Response(member_data)

    @action(
        detail=False,
        methods=["PATCH"],
        url_path=r"(?P<member_id>[\d]+)/status",  # noqa: W605
    )
    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @load_object("member", models.InternetExchangeMember, ix="ix", id="member_id")
    @grainy_endpoint(
        namespace="member.{request.org.permission_id}.{ix.pk}",
    )
    def status(self, request, org, instance, ix, member_id, member, *args, **kwargs):
        """
        Update the status of a specified Internet Exchange Member.

        This method handles PATCH requests to update the status of an Internet Exchange
        member. It performs the following tasks:
          1. Retrieves and deserializes the supplied request data.
          2. Validates the deserialized data.
          3. Updates the member's status if the data is valid.
          4. Returns a serialized representation of the updated member.

        Note:
          This method is decorated with several decorators:
          - `@action`: Configures this method as a custom endpoint for PATCH requests.
          - `@load_object`: Retrieves the InternetExchange and InternetExchangeMember instances.
          - `@grainy_endpoint`: Applies granular permission control.

        Args:
          request (Request): The request object containing the data to update.
          org (Organization): The organization associated with the request.
          instance (InternetExchange): The InternetExchange instance.
          ix (InternetExchange): The loaded InternetExchange object.
          member_id (int): The ID of the InternetExchangeMember to update.
          member (InternetExchangeMember): The InternetExchangeMember instance to update.
          *args: Variable length argument list.
          **kwargs: Arbitrary keyword arguments.

        Returns:
          Response: A Response object containing the serialized data of the updated member
          if the serializer is valid. Otherwise, returns the serializer errors.
        """
        serializer = self.serializer_class(
            member,
            data=request.data,
            partial=True,
            context={"instance": instance},
        )
        if serializer.is_valid():
            # Update the member status
            updated_instance = serializer.save()
            updated_serializer = self.serializer_class(updated_instance)

            # Update the physical ports status in deviceCtl
            models.InternetExchangeMember.set_ports_status(
                member=member,
                status=serializer.validated_data.get("status"),
            )
            return Response(updated_serializer.data)

        logger.debug(f"{serializer.errors=}")
        return Response(serializer.errors)

    @action(detail=False, methods=["GET"], url_path=r"port/(?P<port_id>\d+)/metric")
    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @grainy_endpoint(
        namespace="member.{request.org.permission_id}.{ix.pk}",
    )
    def ix_metric(self, request, org, instance, ix, port_id, *args, **kwargs):
        metric_data = devicectl.VirtualPort().metric(port_id)
        serilizer = Serializers.ix_metric(data=metric_data, many=True)
        serilizer.is_valid(raise_exception=True)
        return Response(serilizer.validated_data)


@route
class Routeserver(CachedObjectMixin, IxOrgQuerysetMixin, viewsets.GenericViewSet):
    serializer_class = Serializers.routeserver
    queryset = models.Routeserver.objects.all()
    ref_tag = "routeserver"
    ix_tag_needed = True
    lookup_url_kwarg = "routeserver_id"
    lookup_field = "id"

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @grainy_endpoint(
        namespace="routeserver.{request.org.permission_id}.{ix.pk}.?",
        handlers={"*": {"key": lambda row, idx: row["asn"]}},
    )
    def list(self, request, org, instance, ix, *args, **kwargs):
        queryset = self.get_queryset().order_by("name")
        ordering_filter = CaseInsensitiveOrderingFilter(["name", "asn", "router_id"])
        queryset = ordering_filter.filter_queryset(request, queryset, self)
        serializer = Serializers.routeserver(
            instance=queryset,
            many=True,
        )
        models.Routeserver.preload_events(queryset)
        liveness_event = auditctl.Event().get_last_updated_config_liveness_event(
            org.slug
        )

        routeserver_event_map = {}
        for routeserver in queryset:
            routeserver_event_map[routeserver.id] = (
                routeserver._event_object
                if hasattr(routeserver, "_event_object")
                else None
            )

        routeservers = serializer.data
        for routeserver in routeservers:
            routeserver["bgp_stat_aggregate"] = None
            routeserver["config_last_fetched_time"] = None
            event = routeserver_event_map.get(routeserver.get("id"))
            if event:
                routeserver["bgp_stat_aggregate"] = event.data.components
                routeserver["config_last_fetched_time"] = (
                    datetime.fromisoformat(liveness_event[0].get("created")).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    if liveness_event
                    else None
                )
        return Response(routeservers)

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @auditlog()
    @grainy_endpoint(
        namespace="routeserver.{request.org.permission_id}.{ix.pk}.?",
        handlers={"*": {"key": lambda row, idx: row["asn"]}},
    )
    def create(self, request, org, instance, ix, *args, **kwargs):
        data = request.data
        data["ix"] = models.InternetExchange.objects.get(instance=instance, id=ix.pk).id
        serializer = Serializers.routeserver(data=data, context={"instance": instance})
        if not serializer.is_valid():
            return BadRequest(serializer.errors)

        routeserver = serializer.save()

        return Response(Serializers.routeserver(instance=routeserver).data)

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @load_object("routeserver", models.Routeserver, ix="ix", id="routeserver_id")
    @auditlog()
    @grainy_endpoint(
        namespace="routeserver.{request.org.permission_id}.{ix.pk}.{routeserver_id}",
    )
    def update(self, request, org, instance, ix, routeserver, *args, **kwargs):
        serializer = Serializers.routeserver(
            data=request.data, instance=routeserver, context={"instance": instance}
        )
        if not serializer.is_valid():
            return BadRequest(serializer.errors)

        routeserver = serializer.save()

        return Response(Serializers.routeserver(instance=routeserver).data)

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @load_object("routeserver", models.Routeserver, ix="ix", id="routeserver_id")
    @auditlog()
    @grainy_endpoint(
        namespace="routeserver.{request.org.permission_id}.{ix.pk}.{routeserver_id}",
    )
    def destroy(self, request, org, instance, ix, routeserver, *args, **kwargs):
        r = Response(Serializers.routeserver(instance=routeserver).data)
        routeserver.delete()
        return r

    @action(detail=True, methods=["POST"])
    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @load_object("routeserver", models.Routeserver, ix="ix", id="routeserver_id")
    @grainy_endpoint(
        namespace="routeserver.{request.org.permission_id}.{ix.pk}.{routeserver_id}",
    )
    def operational_status(
        self, request, org, instance, ix, routeserver, *args, **kwargs
    ):
        serializer = OperationalStatusSerializer(data=request.data)
        if serializer.is_valid():
            operational_status = serializer.validated_data.get("operational_status")
            routeserver.operational_status = operational_status
            routeserver.save()
            serializer = Serializers.routeserver(
                instance=routeserver,
                many=False,
            )
            return Response(serializer.data)
        else:
            return Response(serializer.errors, status=400)


@route
class BGPSessionState(OrgQuerysetMixin, viewsets.GenericViewSet):
    """
    Endpoint for updating and deleting bgp session state
    based on peer asn, and peer ip
    """

    serializer_class = Serializers.bgp_state
    ref_tag = "bgp_state"

    @action(
        detail=False,
        methods=["put"],
        url_path="(?P<routeserver_router_id>[^/]+)/(?P<asn>[^/]+)/update",
    )
    def update_bgp_state(
        self, request, org, routeserver_router_id, asn, *args, **kwargs
    ):
        """
        Handles saving of bgp state data
        Unique sessions are identified by peer asn + peer ip
        """
        serializer = self.serializer_class(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        members = set()
        for component in serializer.validated_data:
            filters = {
                "asn": int(asn),
                "is_rs_peer": True,
                "ix__verified": True,
            }
            if ipaddress.ip_address(component.get("address")).version == 4:
                filters["ipaddr4"] = component.get("address")
            else:
                filters["ipaddr6"] = component.get("address")

            members.add(models.InternetExchangeMember.objects.get(**filters))

        physical_port_stats_bridge = devicectl.PhysicalPortStats()

        for member in members:
            for physical_port in member.physical_ports:
                physical_port_stats_bridge.save_physical_port_stats(
                    data=serializer.validated_data,
                    org_slug=org.slug,
                    physical_port=physical_port,
                    stat_type="bgp_stats",
                )
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["delete"],
        url_path="(?P<member_id>[^/]+)/delete",
    )
    @grainy_endpoint(namespace="verified.asn.{asn}.?")
    def delete_bgp_state(self, request, org, member_id, *args, **kwargs):
        """
        Handles deletion of bgp state data
        Unique sessions are identified by peer asn + peer ip
        """
        try:
            member = models.InternetExchangeMember.objects.get(id=member_id)
        except models.InternetExchangeMember.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        physical_port_stats_bridge = devicectl.PhysicalPortStats()

        for physical_port in member.physical_ports:
            physical_port_stats = list(
                physical_port_stats_bridge.objects(physical_port=physical_port)
            )
            if physical_port_stats:
                physical_port_stats_bridge.delete(obj=physical_port_stats[0])

        return Response(status=status.HTTP_204_NO_CONTENT)


@route
class RouteserverConfig(CachedObjectMixin, IxOrgQuerysetMixin, viewsets.GenericViewSet):
    serializer_class = Serializers.config__routeserver
    queryset = models.RouteserverConfig.objects.all()
    lookup_value_regex = r"[^\/]+"  # noqa: W605
    lookup_url_kwarg = "name"
    lookup_field = "routeserver__name"
    ref_tag = "config/routeserver"
    ix_tag_needed = True
    ix_lookup_field = "routeserver__ix"

    def options(self, request, *args, **kwargs):
        """
        Overrides the default OPTIONS request handling
        so we can include a Last-Modified header for the specified
        routeserver config object in the response.
        """

        # only proceed if ix_tag and name are specified

        if "ix_tag" in kwargs and "name" in kwargs:
            # check if the routeserver config object exists

            try:
                rs_config = models.RouteserverConfig.objects.get(
                    routeserver__name=kwargs["name"],
                    routeserver__ix__slug=kwargs["ix_tag"],
                    routeserver__ix__instance__org__slug=request.org.slug,
                )
            except models.RouteserverConfig.DoesNotExist:
                return Response(status=404)

            # if it does, include a Last-Modified header

            return self._options(request, rs_config)

        return super().options(request, *args, **kwargs)

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @grainy_endpoint(
        namespace="config.routeserver.{request.org.permission_id}",
    )
    def retrieve(self, request, org, instance, ix, name, *args, **kwargs):
        rs_config = models.RouteserverConfig.objects.get(
            routeserver__name=name, routeserver__ix=ix
        )

        serializer = Serializers.config__routeserver(
            instance=rs_config,
            many=False,
        )
        return Response(serializer.data)

    @action(
        detail=True, methods=["GET", "OPTIONS"], renderer_classes=[PlainTextRenderer]
    )
    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @grainy_endpoint(
        namespace="config.routeserver.{request.org.permission_id}",
    )
    def plain(self, request, org, instance, ix, name, *args, **kwargs):
        rs_config = models.RouteserverConfig.objects.get(
            routeserver__name=name, routeserver__ix=ix
        )

        if request.method == "OPTIONS":
            return self._options(request, rs_config)

        serializer = Serializers.config__routeserver(
            instance=rs_config,
            many=False,
        )
        # return Response(serializer.instance.body)
        return Response(serializer.instance.body)

    @action(detail=True, methods=["POST"])
    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @grainy_endpoint(
        namespace="config.routeserver.{request.org.permission_id}",
    )
    def status(self, request, org, instance, ix, name, *args, **kwargs):
        rs_config = self.get_object()
        rs_config.rs_response = request.data
        rs_config.save()
        serializer = Serializers.config__routeserver(
            instance=rs_config,
            many=False,
        )
        return Response(serializer.data)

    def _options(self, request, rs_config):
        response = Response(self.metadata_class().determine_metadata(request, self))
        response.headers["Last-Modified"] = rs_config.generated.strftime(
            "%a, %d %b %Y %H:%M:%S GMT"
        )
        return response

    @action(detail=True, methods=["POST"])
    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @grainy_endpoint(
        namespace="config.routeserver.{request.org.permission_id}",
    )
    def generate(self, request, org, instance, ix, name, *args, **kwargs):
        rs_config = self.get_object()
        rs_config.queue_generate()
        serializer = Serializers.config__routeserver(
            instance=rs_config,
            many=False,
        )
        return Response(serializer.data)


@route
class PeeringDBRouteservers(
    CachedObjectMixin, IxOrgQuerysetMixin, viewsets.GenericViewSet
):
    serializer_class = Serializers.pdbrouteserver
    queryset = models.Routeserver.objects.all()
    ix_tag_needed = True
    ref_tag = "pdbrouteserver"

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @grainy_endpoint(namespace="routeserver.{request.org.permission_id}")
    def list(self, request, org, instance, ix, *args, **kwargs):
        if not ix.pdb_id:
            return Response(self.serializer_class([], many=True).data)
        candidates = list(pdbctl.NetworkIXLan().objects(ix=ix.pdb_id, routeserver=1))
        return Response(self.serializer_class(candidates, many=True).data)


@route
class Network(CachedObjectMixin, OrgQuerysetMixin, viewsets.GenericViewSet):
    serializer_class = Serializers.net
    queryset = models.Network.objects.all()

    lookup_url_kwarg = "asn"
    lookup_field = "asn"

    @grainy_endpoint(namespace="net.{request.org.permission_id}")
    def list(self, request, org, instance, *args, **kwargs):
        serializer = Serializers.net(
            instance.net_set.all(),
            many=True,
        )
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["GET"],
        url_path=r"presence/(?P<asn>[\d]+)",  # noqa: W605
    )
    @grainy_endpoint(namespace="net.{request.org.permission_id}.{asn}")
    @load_object("net", models.Network, asn="asn", instance="instance")
    def presence(self, request, org, instance, asn, net=None, *args, **kwargs):
        serializer = Serializers.presence(
            net.members,
            many=True,
            context={"perms": request.perms, "user": request.user},
        )
        return Response(serializer.data)


@route
class PermissionRequest(CachedObjectMixin, viewsets.GenericViewSet):
    serializer_class = Serializers.permreq
    queryset = models.PermissionRequest.objects.all()

    @grainy_endpoint()
    def list(self, request, org, *args, **kwargs):
        serializer = Serializers.permreq(
            org.permreq_set.all(),
            many=True,
            context={
                "user": request.user,
                "perms": request.perms,
            },
        )
        return Response(serializer.data)

    """
    @grainy_endpoint(namespace="?.?")
    def create(self, request, org, instance, *args, **kwargs):
        data = request.data
        data["user"] = request.user.id
        data["org"] = org.id
        serializer = Serializers.permreq(data=data)

        if not serializer.is_valid():
            return BadRequest(serializer.errors)

        permreq = serializer.save()
        return Response(serializer.data)
    """


@route
class TrafficAlertConfig(IxOrgQuerysetMixin, viewsets.GenericViewSet):
    serializer_class = Serializers.traffic_alert_config
    queryset = models.TrafficAlertConfig.objects.all()
    ix_tag_needed = True
    lookup_field = "id"
    lookup_url_kwarg = "id"

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @auditlog()
    @grainy_endpoint(namespace="ix.{request.org.permission_id}")
    def create(self, request, org, instance, ix, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @load_object("traffic_alert_config", models.TrafficAlertConfig, ix="ix", id="id")
    @grainy_endpoint(namespace="ix.{request.org.permission_id}")
    def retrieve(
        self, request, org, instance, ix, traffic_alert_config, *args, **kwargs
    ):
        serializer = self.serializer_class(instance=traffic_alert_config)
        return Response(serializer.data)

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @load_object("traffic_alert_config", models.TrafficAlertConfig, ix="ix", id="id")
    @auditlog()
    @grainy_endpoint(namespace="ix.{request.org.permission_id}")
    def update(self, request, org, instance, ix, traffic_alert_config, *args, **kwargs):
        serializer = self.serializer_class(
            data=request.data, instance=traffic_alert_config, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(detail=False, methods=["GET"])
    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @load_object("traffic_alert_config", models.TrafficAlertConfig, ix="ix")
    @grainy_endpoint(namespace="ix.{request.org.permission_id}")
    def get_by_ix(
        self, request, org, instance, ix, traffic_alert_config, *args, **kwargs
    ):
        serializer = self.serializer_class(instance=traffic_alert_config)
        return Response(serializer.data)


@route
class EmailTemplate(IxOrgQuerysetMixin, viewsets.GenericViewSet):
    serializer_class = Serializers.email_template
    queryset = models.EmailTemplate.objects.all()
    ix_tag_needed = True
    lookup_field = "id"
    lookup_url_kwarg = "id"

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @grainy_endpoint(namespace="ix.{request.org.permission_id}")
    def list(self, request, org, instance, ix, *args, **kwargs):
        email_templates = models.EmailTemplate.objects.filter(ix=ix)
        # if not email_templates:
        #     email_templates = self.get_default_templates(ix)
        serializer = self.serializer_class(email_templates, many=True)
        return Response(serializer.data)

    def get_default_templates(self, ix):
        email_templates = []
        for template_type, template_name in models.EMAIL_TEMPLATE_TYPES:
            email_template = models.EmailTemplate(
                id=0,
                ix=ix,
                type=template_type,
                name=template_name,
            )
            path = os.path.join(
                email_template.template_loader_paths[0], email_template.template_path
            )
            with open(path) as fh:
                email_template.body = fh.read()
            email_templates.append(email_template)
        return email_templates

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @auditlog()
    @grainy_endpoint(namespace="ix.{request.org.permission_id}")
    def create(self, request, org, instance, ix, *args, **kwargs):
        serializer = self.serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["get"],
        url_path="default_template/(?P<template_type>[^/]+)",
    )
    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @grainy_endpoint(namespace="ix.{request.org.permission_id}")
    def get_default_by_type(
        self, request, org, instance, ix, template_type, *args, **kwargs
    ):
        email_template = None
        try:
            email_template = models.EmailTemplate.objects.get(ix=ix, type=template_type)
        except models.EmailTemplate.DoesNotExist:
            for template in self.get_default_templates(ix):
                if template.type == template_type:
                    email_template = template
                    break
        if not email_template:
            return Response(status=404)
        serializer = self.serializer_class(email_template)
        return Response(serializer.data)

    @action(detail=False, methods=["post"], url_path="(?P<template_id>[^/]+)/preview")
    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @grainy_endpoint(namespace="ix.{request.org.permission_id}")
    def preview(self, request, org, instance, ix, template_id, *args, **kwargs):
        if template_id == "0":
            email_template = models.EmailTemplate(
                id=0,
                ix=ix,
                name="Preview",
                type=request.data.get("type"),
                body=request.data.get("body"),
            )
        else:
            email_template = models.EmailTemplate.objects.get(id=template_id)
            email_template.body = request.data.get("body")
        serializer = Serializers.template_preview(instance=email_template)
        return Response(serializer.data)

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @load_object("email_template", models.EmailTemplate, ix="ix", id="id")
    @grainy_endpoint(namespace="ix.{request.org.permission_id}.{ix.pk}")
    def retrieve(self, request, org, instance, ix, email_template, *args, **kwargs):
        serializer = self.serializer_class(instance=email_template)
        return Response(serializer.data)

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @load_object("email_template", models.EmailTemplate, ix="ix", id="id")
    @auditlog()
    @grainy_endpoint(namespace="ix.{request.org.permission_id}")
    def update(self, request, org, instance, ix, email_template, *args, **kwargs):
        serializer = self.serializer_class(
            instance=email_template, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    @load_object("ix", models.InternetExchange, instance="instance", slug="ix_tag")
    @load_object("email_template", models.EmailTemplate, ix="ix", id="id")
    @auditlog()
    @grainy_endpoint(namespace="ix.{request.org.permission_id}.{ix.pk}")
    def destroy(self, request, org, instance, ix, email_template, *args, **kwargs):
        response = Response(self.serializer_class(instance=email_template).data)
        email_template.delete()
        return response
