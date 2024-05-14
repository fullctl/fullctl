import json
import os
import time

import fullctl.service_bridge.pdbctl as pdbctl
from django.conf import settings
from fullctl.django.auditlog import auditlog
from fullctl.django.decorators import service_bridge_sync
from fullctl.django.rest.core import BadRequest
from fullctl.django.rest.decorators import load_object
from fullctl.django.rest.filters import CaseInsensitiveOrderingFilter
from fullctl.django.rest.mixins import (  # ContainerQuerysetMixin,; OrgQuerysetMixin,
    CachedObjectMixin,
)
from fullctl.django.rest.renderers import PlainTextRenderer
from fullctl.graph.mrtg import rrd as mrtg_rrd
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

import django_devicectl.models as models
import django_devicectl.traffic as traffic
from django_devicectl.rest.decorators import grainy_endpoint
from django_devicectl.rest.route.devicectl import route
from django_devicectl.rest.serializers.devicectl import Serializers


@route
class Facility(CachedObjectMixin, viewsets.GenericViewSet):
    serializer_class = Serializers.facility
    queryset = models.Facility.objects.all()
    lookup_url_kwarg = "facility_tag"
    ref_tag = "facility"
    lookup_field = "slug"

    def get_queryset(self):
        qset = super().get_queryset()
        return qset.filter(instance__org__slug=self.kwargs["org_tag"])

    # def get_queryset(self):
    #    return super().get_queryset().filter(instance__org__slug=self.kwargs["org_tag"])

    @grainy_endpoint(namespace="facility.{request.org.permission_id}")
    @service_bridge_sync(pull="sot")
    def list(self, request, org, instance, *args, **kwargs):
        # ordering_filter = CaseInsensitiveOrderingFilter(["name", "type"])

        queryset = instance.facilities.all().order_by("slug")
        # queryset = ordering_filter.filter_queryset(request, queryset, self)

        serializer = Serializers.facility(
            queryset,
            many=True,
        )
        return Response(serializer.data)

    @load_object("facility", models.Facility, instance="instance", slug="facility_tag")
    @grainy_endpoint(namespace="facility.{request.org.permission_id}.{facility_tag}")
    @service_bridge_sync(pull="sot")
    def retrieve(self, request, org, instance, facility, *args, **kwargs):
        serializer = Serializers.facility(
            instance=facility,
            many=False,
        )
        return Response(serializer.data)

    @auditlog()
    @grainy_endpoint(namespace="facility.{request.org.permission_id}")
    @service_bridge_sync(push=True)
    def create(self, request, org, instance, *args, **kwargs):
        data = request.data
        data["instance"] = instance.id

        serializer = Serializers.facility(data=data)
        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        facility = serializer.save()

        return Response(Serializers.facility(instance=facility).data)

    @auditlog()
    @grainy_endpoint(namespace="facility.{request.org.permission_id}.{facility_tag}")
    @load_object("facility", models.Facility, instance="instance", slug="facility_tag")
    @service_bridge_sync(push=True)
    def update(self, request, org, instance, facility, *args, **kwargs):
        request.data["instance"] = instance.id

        serializer = Serializers.facility(
            facility,
            data=request.data,
        )

        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        facility = serializer.save()

        return Response(Serializers.facility(instance=facility).data)

    @auditlog()
    @grainy_endpoint(namespace="facility.{request.org.permission_id}.{facility_tag}")
    @load_object("facility", models.Facility, instance="instance", slug="facility_tag")
    def destroy(self, request, org, instance, facility, *args, **kwargs):
        r = Response(Serializers.facility(instance=facility).data)
        facility.delete()
        return r

    @action(
        detail=True, methods=["POST"], serializer_class=Serializers.facility_add_device
    )
    @grainy_endpoint(namespace="device.{request.org.permission_id}")
    @load_object("facility", models.Facility, instance="instance", slug="facility_tag")
    @service_bridge_sync(push=True)
    def add_device(self, request, org, instance, facility, *args, **kwargs):
        device = models.Device.objects.get(
            instance=instance, id=request.data.get("device")
        )
        device.facility = facility
        device.save()

        serializer = Serializers.device(device)

        return Response(serializer.data)

    @action(
        detail=True, methods=["DELETE"], url_path="remove_device/(?P<device_id>[^/.]+)"
    )
    @grainy_endpoint(namespace="device.{request.org.permission_id}")
    @load_object(
        "device",
        models.Device,
        instance="instance",
        facility__slug="facility_tag",
        id="device_id",
    )
    @load_object("facility", models.Facility, instance="instance", slug="facility_tag")
    @service_bridge_sync(push=True)
    def remove_device(self, request, org, instance, facility, device, *args, **kwargs):
        serializer = Serializers.device(device)
        response = Response(serializer.data)

        if settings.SERVICE_BRIDGE_REF_DEVICE and device.reference:
            device.facility = None
            device.save()
        else:
            device.delete()

        return response

    @action(detail=True, serializer_class=Serializers.device)
    @grainy_endpoint(namespace="device.{request.org.permission_id}")
    @service_bridge_sync(pull="sot")
    def devices(self, request, org, instance, *args, **kwargs):
        ordering_filter = CaseInsensitiveOrderingFilter(["name", "type", "status"])
        facility = self.get_object()

        queryset = facility.devices.all()

        if request.GET.get("include-unassigned"):
            queryset |= models.Device.objects.filter(facility__isnull=True)

        queryset = queryset.order_by("name")
        queryset = ordering_filter.filter_queryset(request, queryset, self)

        serializer = Serializers.device(
            queryset,
            many=True,
        )

        return Response(serializer.data)

    @action(detail=True, serializer_class=Serializers.logical_port)
    @grainy_endpoint(namespace="logical_port.{request.org.permission_id}")
    @load_object("facility", models.Facility, instance="instance", slug="facility_tag")
    def logical_ports(self, request, org, instance, facility, *args, **kwargs):
        ordering_filter = CaseInsensitiveOrderingFilter(["name", "channel", "trunk"])
        queryset = facility.logical_ports
        queryset = ordering_filter.filter_queryset(request, queryset, self)

        serializer = Serializers.logical_port(
            queryset,
            many=True,
        )
        return Response(serializer.data)


@route
class Device(CachedObjectMixin, viewsets.GenericViewSet):
    serializer_class = Serializers.device
    queryset = models.Device.objects.all()
    lookup_url_kwarg = "device_id"
    ref_tag = "device"
    lookup_field = "id"

    @grainy_endpoint(namespace="device.{request.org.permission_id}")
    def list(self, request, org, instance, *args, **kwargs):
        queryset = instance.devices.all()
        queryset = (
            queryset.select_related("facility")
            .order_by("operational_status__status", "name")
            .exclude(name__startswith="peerctl:")
        )

        serializer = Serializers.device(
            queryset,
            many=True,
        )
        return Response(serializer.data)

    @action(detail=False)
    @grainy_endpoint(namespace="device.{request.org.permission_id}")
    def list_unassigned(self, request, org, instance, *args, **kwargs):
        ordering_filter = CaseInsensitiveOrderingFilter(["name", "type"])
        queryset = instance.devices.filter(facility__isnull=True)
        queryset = ordering_filter.filter_queryset(request, queryset, self)
        serializer = Serializers.device(
            queryset,
            many=True,
        )
        return Response(serializer.data)

    @grainy_endpoint(namespace="device.{request.org.permission_id}.{device_id}")
    @load_object("device", models.Device, instance="instance", id="device_id")
    @service_bridge_sync(pull="sot")
    def retrieve(self, request, org, instance, device, *args, **kwargs):
        serializer = Serializers.device(
            instance=device,
            many=False,
        )
        return Response(serializer.data)

    @action(detail=True, serializer_class=Serializers.device_operational_status)
    @grainy_endpoint(namespace="device.{request.org.permission_id}.{device_id}")
    @load_object("device", models.Device, instance="instance", id="device_id")
    def operational_status(self, request, org, instance, device, *args, **kwargs):
        serializer = Serializers.device_operational_status(
            device.operational_status,
        )
        return Response(serializer.data)

    @action(
        detail=True,
        serializer_class=Serializers.device_config,
        url_path="config/current",
    )
    @grainy_endpoint(namespace="device.{request.org.permission_id}.{device_id}")
    @load_object("device", models.Device, instance="instance", id="device_id")
    def current_config(self, request, org, instance, device, *args, **kwargs):
        """
        Returns the current config of the device (normal api json response)
        """

        config = device.operational_status.get_current_config()

        if config:
            url = config.url_current
            config = config.config_current
        else:
            url = None
            config = None

        serializer = Serializers.device_config(
            {
                "id": device.id,
                "config": config,
                "url": url,
            },
        )
        return Response(serializer.data)

    @action(
        detail=True,
        serializer_class=Serializers.device_config,
        renderer_classes=[PlainTextRenderer],
        url_path="config/current/plain",
    )
    @grainy_endpoint(namespace="device.{request.org.permission_id}.{device_id}")
    @load_object("device", models.Device, instance="instance", id="device_id")
    def current_config_plain(self, request, org, instance, device, *args, **kwargs):
        """
        Returns the current config of the device (plain-text response)
        """

        config = device.operational_status.get_current_config()

        if config:
            config = config.config_current

        serializer = Serializers.device_config(
            {"id": device.id, "config": config},
        )
        return Response(serializer.data["config"])

    @action(
        detail=True,
        serializer_class=Serializers.device_config,
        url_path="config/reference",
    )
    @grainy_endpoint(namespace="device.{request.org.permission_id}.{device_id}")
    @load_object("device", models.Device, instance="instance", id="device_id")
    def reference_config(self, request, org, instance, device, *args, **kwargs):
        """
        Returns the reference config of the device (normal api json response)
        """

        config = device.operational_status.get_reference_config()

        if config:
            url = config.url_reference
            config = config.config_reference
        else:
            url = None
            config = None

        serializer = Serializers.device_config(
            {
                "id": device.id,
                "config": config,
                "url": url,
            },
        )
        return Response(serializer.data)

    @action(
        detail=True,
        serializer_class=Serializers.device_config,
        renderer_classes=[PlainTextRenderer],
        url_path="config/reference/plain",
    )
    @grainy_endpoint(namespace="device.{request.org.permission_id}.{device_id}")
    @load_object("device", models.Device, instance="instance", id="device_id")
    def reference_config_plain(self, request, org, instance, device, *args, **kwargs):
        """
        Returns the reference config of the device (plain-text response)
        """
        config = device.operational_status.get_reference_config()

        if config:
            config = config.config_reference

        serializer = Serializers.device_config(
            {"id": device.id, "config": config},
        )
        return Response(serializer.data["config"])

    @action(
        detail=True, serializer_class=Serializers.device_config, url_path="config/diff"
    )
    @grainy_endpoint(namespace="device.{request.org.permission_id}.{device_id}")
    @load_object("device", models.Device, instance="instance", id="device_id")
    def diff_config(self, request, org, instance, device, *args, **kwargs):
        """
        Returns the diff between the current and reference config of the device (normal api json response)
        """

        serializer = Serializers.device_config(
            {"id": device.id, "config": models.DeviceConfigHistory.diff(device)},
        )
        return Response(serializer.data)

    @action(
        detail=True,
        serializer_class=Serializers.device_config,
        renderer_classes=[PlainTextRenderer],
        url_path="config/diff/plain",
    )
    @grainy_endpoint(namespace="device.{request.org.permission_id}.{device_id}")
    @load_object("device", models.Device, instance="instance", id="device_id")
    def diff_config_plain(self, request, org, instance, device, *args, **kwargs):
        """
        Returns the diff between the current and reference config of the device (plain-text response)
        """

        serializer = Serializers.device_config(
            {"id": device.id, "config": models.DeviceConfigHistory.diff(device)},
        )
        return Response(serializer.data["config"])

    @action(
        detail=True,
        serializer_class=Serializers.device_config_history,
        url_path="config/history",
    )
    @grainy_endpoint(namespace="device.{request.org.permission_id}.{device_id}")
    @load_object("device", models.Device, instance="instance", id="device_id")
    def config_history(self, request, org, instance, device, *args, **kwargs):
        """
        Returns the config history of the device
        """

        queryset = device.config_history.order_by("-created")[:255]
        serializer = Serializers.device_config_history(
            queryset,
            many=True,
        )
        return Response(serializer.data)

    @action(
        detail=True,
        serializer_class=Serializers.device_referee_report,
        url_path="reports",
    )
    @grainy_endpoint(namespace="device.{request.org.permission_id}.{device_id}")
    @load_object("device", models.Device, instance="instance", id="device_id")
    def reports(self, request, org, instance, device, *args, **kwargs):
        """
        Lists referee reports for this device
        """

        # get most recent config history entry to determine cutoff date

        config_history = device.config_history.order_by("-created").first()

        if not config_history:
            return Response([])

        cutoff_date = config_history.created

        # get most recent referee reports

        queryset = device.referee_reports.filter(created__gte=cutoff_date).order_by(
            "-created"
        )

        serializer = Serializers.device_referee_report(
            queryset,
            many=True,
        )
        return Response(serializer.data)

    @action(
        detail=True,
        serializer_class=Serializers.device_referee_report,
        url_path="reports/(?P<report_id>[^/.]+)",
    )
    @grainy_endpoint(namespace="device.{request.org.permission_id}.{device_id}")
    @load_object("device", models.Device, instance="instance", id="device_id")
    def report(self, request, org, instance, device, report_id, *args, **kwargs):
        """
        Single referee reports for this device by report id.

        Will return report data in `report_data`
        """
        serializer = Serializers.device_referee_report(
            models.DeviceRefereeReport.objects.get(id=report_id, device=device),
        )
        return Response(serializer.data)

    @action(
        detail=True,
        serializer_class=Serializers.device_referee_report,
        renderer_classes=[PlainTextRenderer],
        url_path="reports/(?P<report_id>[^/.]+)/plain",
    )
    @grainy_endpoint(namespace="device.{request.org.permission_id}.{device_id}")
    @load_object("device", models.Device, instance="instance", id="device_id")
    def report_plain(self, request, org, instance, device, report_id, *args, **kwargs):
        """
        Single referee report for this device by report id.

        Will return report data as plain text
        """
        serializer = Serializers.device_referee_report(
            models.DeviceRefereeReport.objects.get(id=report_id, device=device),
        )
        return Response(json.dumps(serializer.data["report_data"], indent=4))

    @action(detail=True, serializer_class=Serializers.virtual_port)
    @grainy_endpoint(namespace="virtual_port.{request.org.permission_id}")
    @load_object("device", models.Device, instance="instance", id="device_id")
    def virtual_ports(self, request, org, instance, device, *args, **kwargs):
        ordering_filter = CaseInsensitiveOrderingFilter(["name", "vlan_id"])
        queryset = device.virtual_ports
        queryset = ordering_filter.filter_queryset(request, queryset, self)

        serializer = Serializers.virtual_port(
            queryset,
            many=True,
        )
        return Response(serializer.data)

    @action(detail=True, serializer_class=Serializers.logical_port)
    @grainy_endpoint(namespace="logical_port.{request.org.permission_id}")
    @load_object("device", models.Device, instance="instance", id="device_id")
    def logical_ports(self, request, org, instance, device, *args, **kwargs):
        ordering_filter = CaseInsensitiveOrderingFilter(["name", "channel", "trunk"])
        queryset = device.logical_ports
        queryset = ordering_filter.filter_queryset(request, queryset, self)

        serializer = Serializers.logical_port(
            queryset,
            many=True,
        )
        return Response(serializer.data)

    @action(detail=True, serializer_class=Serializers.physical_port)
    @grainy_endpoint(namespace="physical_port.{request.org.permission_id}")
    @load_object("device", models.Device, instance="instance", id="device_id")
    def physical_ports(self, request, org, instance, device, *args, **kwargs):
        ordering_filter = CaseInsensitiveOrderingFilter(["name"])
        queryset = device.physical_ports
        queryset = ordering_filter.filter_queryset(request, queryset, self)

        serializer = Serializers.physical_port(
            queryset,
            many=True,
        )
        return Response(serializer.data)

    @auditlog()
    @grainy_endpoint(namespace="device.{request.org.permission_id}")
    def create(self, request, org, instance, *args, **kwargs):
        data = request.data
        data["instance"] = instance.id
        serializer = Serializers.device(data=data)
        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        device = serializer.save()

        if request.data.get("facility"):
            device.facility_id = request.data.get("facility")
            device.save()

        return Response(Serializers.device(instance=device).data)

    @auditlog()
    @grainy_endpoint(namespace="device.{request.org.permission_id}.{device_id}")
    @load_object("device", models.Device, instance="instance", id="device_id")
    def update(self, request, org, instance, device, *args, **kwargs):
        request.data["instance"] = instance.id
        serializer = Serializers.device(
            device,
            data=request.data,
        )

        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        device = serializer.save()

        return Response(Serializers.device(instance=device).data)

    @action(detail=True, methods=["patch"], serializer_class=Serializers.device_meta)
    @auditlog()
    @grainy_endpoint(namespace="device.{request.org.permission_id}.{device_id}")
    @load_object("device", models.Device, instance="instance", id="device_id")
    def meta(self, request, org, instance, device_id, device, *args, **kwargs):
        """
        updates device meta
        """

        serializer = Serializers.device_meta(
            device,
            data=request.data,
        )

        if not serializer.is_valid():
            return BadRequest(serializer.errors)

        for k, v in serializer.validated_data.items():
            device.meta[k] = v

        device.save()

        serializer = Serializers.device_meta(data=device.meta)
        serializer.is_valid()

        return Response(serializer.data)

    @auditlog()
    @grainy_endpoint(namespace="device.{request.org.permission_id}.{device_id}")
    @load_object("device", models.Device, instance="instance", id="device_id")
    def destroy(self, request, org, instance, device, *args, **kwargs):
        r = Response(Serializers.device(instance=device).data)
        device.delete()
        return r

    @action(detail=True, methods=["get"])
    @grainy_endpoint(namespace="device.{request.org.permission_id}.{device_id}")
    @load_object("device", models.Device, instance="instance", id="device_id")
    def traffic(self, request, org, instance, device_id, device, *args, **kwargs):
        """
        Returns traffic data points for this specific physical port

        URL Parameters:

        * `start_time` - start time of the traffic data points (int unix epoch)
        * `duration` - duration of the traffic data points (int seconds)
        """

        traffic_data = traffic.get_traffic_for_obj(
            device, request.GET.get("start_time"), request.GET.get("duration")
        )

        return Response(Serializers.device_traffic(instance=traffic_data).data)


class PortTrafficMixin:
    """
    Mixin for port traffic endpoints (both reading and writing)
    """

    def _update_traffic_batch(self, data, context_objs, org=None):
        serializer = Serializers.port_traffic(
            data=data, context={"context_objs": context_objs, "org": org}
        )

        if not serializer.is_valid():
            return BadRequest(serializer.errors)

        serializer.save()
        return Response(serializer.data)

    def _import_traffic_mrtg_batch(self, data, context_objs, org=None):
        serializer = Serializers.port_traffic_mrtg_import_batch(
            data=data, context={"context_objs": context_objs, "org": org}
        )

        if not serializer.is_valid():
            return BadRequest(serializer.errors)

        serializer.save()
        return Response(serializer.data)

    def _get_traffic(self, port, start_time, duration):
        if not start_time:
            start_time = int(time.time())
        else:
            start_time = int(start_time)

        if not duration:
            duration = 86400
        else:
            duration = int(duration)

        if not port.meta or "graph" not in port.meta:
            return Response([])

        graph_file = os.path.join(settings.GRAPHS_PATH, port.meta.get("graph"))

        if not os.path.exists(graph_file):
            return Response({})

        traffic_data = mrtg_rrd.load_rrd_file(graph_file, start_time, duration)
        traffic_data = sorted(traffic_data, key=lambda x: -x["timestamp"])

        # set id on each data point
        for data_point in traffic_data:
            data_point["id"] = port.id

        serializer = Serializers.port_traffic(instance=traffic_data, many=False)

        return Response(serializer.data)


@route
class PhysicalPort(PortTrafficMixin, CachedObjectMixin, viewsets.GenericViewSet):
    serializer_class = Serializers.physical_port
    queryset = models.PhysicalPort.objects.all()

    lookup_url_kwarg = "physical_port_id"
    ref_tag = "physical_port"
    lookup_field = "id"

    @grainy_endpoint(namespace="physical_port.{request.org.permission_id}")
    def list(self, request, org, instance, *args, **kwargs):
        ordering_filter = CaseInsensitiveOrderingFilter(
            ["name", "device", "logical_port"]
        )

        queryset = self.get_queryset().filter(device__instance=instance)
        queryset = ordering_filter.filter_queryset(request, queryset, self)

        serializer = Serializers.physical_port(queryset, many=True)
        return Response(serializer.data)

    @grainy_endpoint(
        namespace="physical_port.{request.org.permission_id}.{physical_port_pk}"
    )
    @load_object(
        "physical_port",
        models.PhysicalPort,
        device__instance="instance",
        id="physical_port_id",
    )
    def retrieve(self, request, org, instance, physical_port, *args, **kwargs):
        serializer = Serializers.physical_port(
            instance=physical_port,
            many=False,
        )
        return Response(serializer.data)

    @auditlog()
    @grainy_endpoint(namespace="physical_port.{request.org.permission_id}")
    def create(self, request, org, instance, *args, **kwargs):
        models.Device.objects.get(instance=instance, id=request.data.get("device"))

        data = request.data

        if not data["logical_port"]:
            logical_port = models.LogicalPort.objects.create(
                instance=instance,
                name=f"{data['name']}:lp",
            )
            data["logical_port"] = logical_port.id

        serializer = Serializers.physical_port(data=request.data)

        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        physical_port = serializer.save()
        physical_port.save()

        return Response(Serializers.physical_port(instance=physical_port).data)

    @auditlog()
    @grainy_endpoint(
        namespace="physical_port.{request.org.permission_id}.{physical_port_id}"
    )
    @load_object(
        "physical_port",
        models.PhysicalPort,
        device__instance="instance",
        id="physical_port_id",
    )
    def update(self, request, org, instance, physical_port, *args, **kwargs):
        serializer = Serializers.physical_port(
            physical_port,
            data=request.data,
        )

        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        physical_port = serializer.save()

        return Response(Serializers.physical_port(instance=physical_port).data)

    @auditlog()
    @grainy_endpoint(
        namespace="physical_port.{request.org.permission_id}.{physical_port_id}"
    )
    @load_object(
        "physical_port",
        models.PhysicalPort,
        device__instance="instance",
        id="physical_port_id",
    )
    def destroy(self, request, org, instance, physical_port, *args, **kwargs):
        r = Response(Serializers.physical_port(instance=physical_port).data)
        physical_port.delete()
        return r

    @action(detail=True, methods=["get"])
    @grainy_endpoint(
        namespace="physical_port.{request.org.permission_id}.{physical_port_id}"
    )
    @load_object(
        "physical_port",
        models.PhysicalPort,
        logical_port__instance="instance",
        id="physical_port_id",
    )
    def traffic(
        self, request, org, instance, physical_port_id, physical_port, *args, **kwargs
    ):
        """
        Returns traffic data points for this specific physical port

        URL Parameters:

        * `start_time` - start time of the traffic data points (int unix epoch)
        * `duration` - duration of the traffic data points (int seconds)
        """

        return self._get_traffic(
            physical_port, request.GET.get("start_time"), request.GET.get("duration")
        )

    @action(detail=False, methods=["post"], url_path="traffic")
    @grainy_endpoint(namespace="physical_port.{request.org.permission_id}")
    def traffic_update(self, request, org, instance, *args, **kwargs):
        """
        Queues a traffic data update for one or multiple physical ports

        The processing is done in a job queue and will not be instantly reflected
        in a query to the traffic endpoint.
        """

        ports = {
            port.id: port
            for port in models.PhysicalPort.objects.filter(
                logical_port__instance=instance,
                id__in=[p["id"] for p in request.data],
            )
        }
        return self._update_traffic_batch(request.data, ports, org=org)

    @action(detail=False, methods=["post"], url_path="traffic/import/mrtg")
    @grainy_endpoint(namespace="physical_port.{request.org.permission_id}")
    def traffic_import_mrtg(self, request, org, instance, *args, **kwargs):
        """
        Queues a traffic data import from MRTG for one or multiple physical ports

        The processing is done in a job queue and will not be instantly reflected
        in a query to the traffic endpoint.
        """

        ports = {
            port.id: port
            for port in models.PhysicalPort.objects.filter(
                logical_port__instance=instance,
                id__in=[p["id"] for p in request.data],
            )
        }
        return self._import_traffic_mrtg_batch(request.data, ports, org=org)


@route
class LogicalPort(CachedObjectMixin, viewsets.GenericViewSet):
    serializer_class = Serializers.logical_port
    queryset = models.LogicalPort.objects.all()
    lookup_url_kwarg = "logical_port_id"
    ref_tag = "logical_port"
    lookup_field = "id"

    @grainy_endpoint(namespace="logical_port.{request.org.permission_id}")
    def list(self, request, org, instance, *args, **kwargs):
        ordering_filter = CaseInsensitiveOrderingFilter(["name", "channel", "trunk"])

        queryset = instance.logical_ports.all()
        queryset = ordering_filter.filter_queryset(request, queryset, self)

        serializer = Serializers.logical_port(
            queryset,
            many=True,
        )
        return Response(serializer.data)

    @grainy_endpoint(
        namespace="logical_port.{request.org.permission_id}.{logical_port_pk}"
    )
    @load_object(
        "logical_port", models.LogicalPort, instance="instance", id="logical_port_id"
    )
    def retrieve(self, request, org, instance, logical_port, *args, **kwargs):
        serializer = Serializers.logical_port(
            instance=logical_port,
            many=False,
        )
        return Response(serializer.data)

    @auditlog()
    @grainy_endpoint(namespace="logical_port.{request.org.permission_id}")
    def create(self, request, org, instance, *args, **kwargs):
        request.data["instance"] = instance.id
        serializer = Serializers.logical_port(data=request.data)
        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        logical_port = serializer.save()
        logical_port.save()

        return Response(Serializers.logical_port(instance=logical_port).data)

    @auditlog()
    @grainy_endpoint(
        namespace="logical_port.{request.org.permission_id}.{logical_port_id}"
    )
    @load_object(
        "logical_port", models.LogicalPort, instance="instance", id="logical_port_id"
    )
    def update(self, request, org, instance, logical_port, *args, **kwargs):
        request.data["instance"] = instance.id
        serializer = Serializers.logical_port(
            logical_port,
            data=request.data,
        )

        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        logical_port = serializer.save()
        logical_port.save()

        return Response(Serializers.logical_port(instance=logical_port).data)

    @auditlog()
    @grainy_endpoint(
        namespace="logical_port.{request.org.permission_id}.{logical_port_id}"
    )
    @load_object(
        "logical_port", models.LogicalPort, instance="instance", id="logical_port_id"
    )
    def destroy(self, request, org, instance, logical_port, *args, **kwargs):
        r = Response(Serializers.logical_port(instance=logical_port).data)
        logical_port.delete()
        return r


@route
class VirtualPort(PortTrafficMixin, CachedObjectMixin, viewsets.GenericViewSet):
    serializer_class = Serializers.virtual_port
    queryset = models.VirtualPort.objects.all()
    lookup_url_kwarg = "virtual_port_id"
    ref_tag = "virtual_port"
    lookup_field = "id"

    @grainy_endpoint(namespace="virtual_port.{request.org.permission_id}")
    def list(self, request, org, instance, *args, **kwargs):
        ordering_filter = CaseInsensitiveOrderingFilter(
            ["name", "vlan_id", "logical_port"]
        )

        queryset = self.get_queryset().filter(logical_port__instance=instance)
        queryset = queryset.select_related("logical_port")
        queryset = ordering_filter.filter_queryset(request, queryset, self)

        serializer = Serializers.virtual_port(
            queryset,
            many=True,
        )
        return Response(serializer.data)

    @grainy_endpoint(
        namespace="virtual_port.{request.org.permission_id}.{virtual_port_id}"
    )
    @load_object(
        "virtual_port",
        models.VirtualPort,
        logical_port__instance="instance",
        id="virtual_port_id",
    )
    def retrieve(self, request, org, instance, virtual_port, *args, **kwargs):
        serializer = Serializers.virtual_port(
            instance=virtual_port,
            many=False,
        )
        return Response(serializer.data)

    @auditlog()
    @grainy_endpoint(namespace="virtual_port.{request.org.permission_id}")
    def create(self, request, org, instance, *args, **kwargs):
        models.LogicalPort.objects.get(
            instance=instance, id=request.data.get("logical_port")
        )
        serializer = Serializers.virtual_port(data=request.data)
        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        virtual_port = serializer.save()
        virtual_port.save()

        return Response(Serializers.virtual_port(instance=virtual_port).data)

    @auditlog()
    @grainy_endpoint(
        namespace="virtual_port.{request.org.permission_id}.{virtual_port_id}"
    )
    @load_object(
        "virtual_port",
        models.VirtualPort,
        logical_port__instance="instance",
        id="virtual_port_id",
    )
    def update(self, request, org, instance, virtual_port, *args, **kwargs):
        serializer = Serializers.virtual_port(
            virtual_port,
            data=request.data,
        )

        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        virtual_port = serializer.save()
        virtual_port.save()

        return Response(Serializers.virtual_port(instance=virtual_port).data)

    @auditlog()
    @grainy_endpoint(
        namespace="virtual_port.{request.org.permission_id}.{virtual_port_id}"
    )
    @load_object(
        "virtual_port",
        models.VirtualPort,
        logical_port__instance="instance",
        id="virtual_port_id",
    )
    def destroy(self, request, org, instance, virtual_port, *args, **kwargs):
        r = Response(Serializers.virtual_port(instance=virtual_port).data)
        virtual_port.delete()
        return r

    @action(detail=True, methods=["get"])
    @grainy_endpoint(
        namespace="virtual_port.{request.org.permission_id}.{virtual_port_id}"
    )
    @load_object(
        "virtual_port",
        models.VirtualPort,
        logical_port__instance="instance",
        id="virtual_port_id",
    )
    def traffic(
        self, request, org, instance, virtual_port_id, virtual_port, *args, **kwargs
    ):
        """
        Returns traffic data points for this specific virtual port

        URL Parameters:

        * `start_time` - start time of the traffic data points (int unix epoch)
        * `duration` - duration of the traffic data points (int seconds)
        """

        return self._get_traffic(
            virtual_port, request.GET.get("start_time"), request.GET.get("duration")
        )

    @action(detail=False, methods=["post"], url_path="traffic")
    @grainy_endpoint(namespace="virtual_port.{request.org.permission_id}")
    def traffic_update(self, request, org, instance, *args, **kwargs):
        """
        Queues a traffic data update for one or multiple virtual ports

        The processing is done in a job queue and will not be instantly reflected
        in a query to the traffic endpoint.
        """

        ports = {
            port.id: port
            for port in models.VirtualPort.objects.filter(
                logical_port__instance=instance,
                id__in=[p["id"] for p in request.data],
            )
        }
        return self._update_traffic_batch(request.data, ports, org=org)

    @action(detail=False, methods=["post"], url_path="traffic/import/mrtg")
    @grainy_endpoint(namespace="virtual_port.{request.org.permission_id}")
    def traffic_import_mrtg(self, request, org, instance, *args, **kwargs):
        """
        Queues a traffic data import from MRTG for one or multiple virtual ports

        The processing is done in a job queue and will not be instantly reflected
        in a query to the traffic endpoint.
        """

        ports = {
            port.id: port
            for port in models.VirtualPort.objects.filter(
                logical_port__instance=instance,
                id__in=[p["id"] for p in request.data],
            )
        }
        return self._import_traffic_mrtg_batch(request.data, ports, org=org)


@route
class PeeringDBFacilities(CachedObjectMixin, viewsets.GenericViewSet):
    serializer_class = Serializers.pdbfacility
    queryset = models.Facility.objects.all()
    ref_tag = "pdbfacility"

    @grainy_endpoint(namespace="facility.{request.org.permission_id}")
    def list(self, request, org, instance, *args, **kwargs):
        q = request.GET.get("q")
        if not q:
            return Response(self.serializer_class([], many=True).data)
        candidates = list(pdbctl.Facility().objects(q=q))
        return Response(self.serializer_class(candidates, many=True).data)


@route
class Port(CachedObjectMixin, viewsets.GenericViewSet):
    serializer_class = Serializers.port
    queryset = models.Port.objects.all()
    lookup_url_kwarg = "port_id"
    ref_tag = "port"
    lookup_field = "id"

    @grainy_endpoint(namespace="port.{request.org.permission_id}")
    def list(self, request, org, instance, *args, **kwargs):
        qset = models.Port.objects.filter(port_info__instance=instance)

        qset = qset.select_related(
            "virtual_port", "virtual_port__logical_port", "port_info"
        )
        qset = qset.prefetch_related(
            "port_info__ips", "virtual_port__logical_port__physical_ports"
        )

        q = request.GET.get("q")
        if q:
            qset = models.Port.search(q, qset).distinct("pk")

        return Response(self.serializer_class(qset, many=True).data)


@route
class TrafficGroup(viewsets.GenericViewSet):
    serializer_class = Serializers.device_group_traffic
    queryset = models.Device.objects.all()
    ref_tag = "traffic"

    def _get_traffic(self, group_type, id, start_time, duration):
        try:
            traffic_data = traffic.get_traffic_for_group(
                group_type, id, start_time, duration
            )
        except ValueError as e:
            return BadRequest(str(e))

        return Response(self.serializer_class(instance=traffic_data, many=False).data)

    @action(detail=False, methods=["get"], url_path="ix/(?P<ix_id>[^/.]+)")
    @grainy_endpoint(namespace="device.{request.org.permission_id}")
    def ix(self, request, org, instance, ix_id, *args, **kwargs):
        """
        Returns traffic data points for this specific physical port

        URL Parameters:

        * `start_time` - start time of the traffic data points (int unix epoch)
        * `duration` - duration of the traffic data points (int seconds)
        """

        return self._get_traffic(
            "ixctl-ix",
            ix_id,
            request.GET.get("start_time"),
            request.GET.get("duration"),
        )
