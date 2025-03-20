import json
import os
import time
from datetime import datetime, timedelta

import fullctl.django.tasks.qualifiers as qualifiers
import fullctl.graph.mrtg.rrd as mrtg_rrd
import fullctl.service_bridge.aaactl as aaactl
import fullctl.service_bridge.auditctl as auditctl
import fullctl.service_bridge.ixctl as ixctl
import fullctl.service_bridge.nautobot as nautobot
import fullctl.service_bridge.pdbctl as pdbctl
import fullctl.service_bridge.peerctl as peerctl
import structlog
from django.conf import settings
from django.utils import timezone
from fullctl.django.models import Task
from fullctl.django.models.concrete import OrganizationFile
from fullctl.django.tasks import register
from fullctl.graph.render.traffic import render_graph
from fullctl.metrics import Metrics, make_metrics
from fullctl.metrics.schema import Point

import django_devicectl.models.devicectl as models
import django_devicectl.mrtg as mrtg
import django_devicectl.sflow as sflow

log = structlog.get_logger("django_structlog")

TIMESERIES_AVAILABLE = settings.TIMESERIES_DB_URL is not None


def default_graph_renderer() -> str | None:
    """
    Will determine which (RRD or Timeseries) is responsible
    for rendering the default PNGs.
    """

    # Legacy RRD graphs are still in use, thus for backwards
    # compatibility pngs rendered from RRD will be used
    if settings.GRAPHS_RRD_ENABLED:
        return "rrd"

    # If timeseries is available, use it
    if settings.TIMESERIES_DB_URL is not None:
        return "victoriametrics"

    return None


class OrgConcurrencyLimit(qualifiers.Base):
    """
    Limits how many instance of the task can be worked on at
    the same time (per organization)
    """

    def __init__(self, limit):
        self.limit = limit

    def __str__(self):
        return f"{self.__class__.__name__} {self.limit}"

    def check(self, task):
        return (
            task.__class__.objects.filter(
                status__in=["running", "pending"],
                queue_id__isnull=False,
                op=task.op,
                org=task.org,
            ).count()
            < self.limit
        )

    def ids(self, task):
        return {
            "org_id": task.org_id,
        }


@register
class NautobotPull(Task):
    """
    Sync data from nautobot API to devicectl
    """

    class TaskMeta:
        limit = 1

    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_nautobot_pull"

    @property
    def generate_limit_id(self):
        return self.org_id

    def run(self, *args, **kwargs):
        instance = models.Instance.objects.get(org_id=self.org_id)

        # TODO allow per organization set up of nautobot url / token

        for n_device in nautobot.Device().objects():
            device, _ = models.Device.objects.get_or_create(
                reference=n_device.id, instance=instance
            )
            device.name = n_device.display
            device.save()


@register
class RequestPeerctlSync(Task):
    """
    Will request peerctl to sync devices and ports from devicectl
    """

    class TaskMeta:
        limit = 1

    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_request_peerctl_sync"

    @property
    def generate_limit_id(self):
        return self.org_id

    def run(self, *args, **kwargs):
        net = peerctl.Network()
        url = f"{net.url_prefix}/{net.ref_tag}/request_devicectl_sync"
        net.post(url, json={"org_id": self.org.remote_id})


@register
class UpdateTrafficGraphs(Task):
    """
    Will update traffic graphs

    Required keyword parameters for `create_task` are

    - `context_model`: `virtual_port` or `physical_port`

    Optional keyword parameters for `create_task` are

    - `update`: list of dicts with keys `id`, `bps_in`, `bps_out`, `bps_in_max`, `bps_out_max`, `timestamp`
    - `import_mrtg`: list of dicts with keys `id`, `log_lines`
    """

    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_update_virtual_port_traffic_graphs"

    class TaskMeta:
        if settings.GRAPHS_RRD_ENABLED:
            qualifiers = [
                # in order to avoid any race conditions when inserting
                # data into graphs, we limit concurrency to 1 per org
                OrgConcurrencyLimit(1),
            ]

    @property
    def context_model(self):
        """
        Returns the context model class based on ref tag value stored
        in the task instance's `param['kwargs']['context_model']` field.
        """

        ref_tag = self.param["kwargs"]["context_model"]

        if ref_tag == "virtual_port":
            return models.VirtualPort
        elif ref_tag == "physical_port":
            return models.PhysicalPort
        else:
            raise ValueError(f"Unknown context model {ref_tag}")

    @property
    def members(self) -> dict:
        """
        Returns a dictionary of ixctl members indexed by port id.

        Will cache the result in the instance to avoid multiple lookups.
        """
        if hasattr(self, "_members"):
            return self._members

        port_ids = []
        all_data = self.param["kwargs"].get("update", []) + self.param["kwargs"].get(
            "import_mrtg", []
        )
        for data in all_data:
            virtual_port = self.context_model.objects.get(id=data["id"])
            port_ids.append(virtual_port.port.id)

        if not port_ids:
            self._members = {}
            return self._members

        port_ids = list(set(port_ids))

        self._members = {
            m.port: m
            for m in ixctl.InternetExchangeMember().objects(
                ports=port_ids, org=self.org.remote_id
            )
        }

        return self._members

    @property
    def exchanges(self) -> dict:
        """
        Returns a dictionary of ixctl exchanges indexed by ix id.

        Will cache the result in the instance to avoid multiple lookups.
        """
        if hasattr(self, "_exchanges"):
            return self._exchanges

        exchange_ids = set()
        for member in self.members.values():
            exchange_ids.add(member.ix_id)

        exchange_ids = list(exchange_ids)
        self._exchanges = {
            ix.id: ix for ix in ixctl.InternetExchange().objects(ids=exchange_ids)
        }
        return self._exchanges

    def run(self, *args, **kwargs):
        processed_port_ids = set()
        for data in sorted(kwargs.get("update", []), key=lambda x: int(x["timestamp"])):
            end_early = self.update_rrd(data)
            processed_port_ids.add(data["id"])
            if end_early:
                break

        self.update_victoriametrics(kwargs.get("update", []))

        for data in kwargs.get("import_mrtg", []):
            self.import_mrtg(data)
            processed_port_ids.add(data["id"])

        if self.context_model == models.PhysicalPort and settings.GRAPHS_RRD_ENABLED:
            UpdateDeviceTrafficGraphs.create_task(
                org=self.org,
                *processed_port_ids,
            )
        else:
            AuditCtlIXTrafficReceived.create_task(
                org=self.org,
                data=kwargs.get("update", []),
            )
            if settings.GRAPHS_RRD_ENABLED:
                # Will aggregate IX traffic graphs for RRD
                # then call RenderTrafficGraphs when done
                UpdateIxctlIxTrafficGraphs.create_task(
                    org=self.org,
                )
            else:
                # Going to VM only we can directly render the graphs
                # without needing to aggregate further
                objects_to_render = [
                    f"ixctl-ix-{ix.id}" for ix in self.exchanges.values()
                ]
                RenderTrafficGraphs.create_task(
                    *objects_to_render,
                    org=self.org,
                )

    def update_victoriametrics(self, all_data: list[dict]):

        if not TIMESERIES_AVAILABLE:
            return

        if not all_data:
            return

        metrics = make_metrics()

        tags_base = {
            "ctl_org_id": self.org.remote_id,
            "ctl_org": self.org.slug,
        }

        members = self.members

        # collect ix ids from ixctl
        points = []
        for data in all_data:
            try:

                virtual_port = self.context_model.objects.get(id=data["id"])

                tags = {
                    **tags_base,
                    "ctl_port_id": data["id"],
                    "ctl_ix_id": members[virtual_port.port.id].ix_id,
                    "ctl_device_id": virtual_port.device.id,
                }

                point = Point(
                    measurement="mrtg",
                    tags=tags,
                    fields={
                        "bps_in": data["bps_in"] * 8,
                        "bps_out": data["bps_out"] * 8,
                        "bps_in_max": data["bps_in_max"] * 8,
                        "bps_out_max": data["bps_out_max"] * 8,
                    },
                    timestamp=data["timestamp"],
                )

                points.append(point)
            except Exception as e:
                log.exception(f"Error processing data point {data}", e=e)
                continue

        if points:
            log.debug("Writing points to victoriametrics", points=points)
            metrics.write_many(points)

    def update_rrd(self, data):
        """
        Update the RRD file for the given context object with the given data point (single data point)
        """

        if not settings.GRAPHS_RRD_ENABLED:
            return

        context_obj = self.context_model.objects.get(id=data["id"])
        bps_in = data["bps_in"]
        bps_out = data["bps_out"]
        timestamp = data["timestamp"]
        bps_in_max = data["bps_in_max"]
        bps_out_max = data["bps_out_max"]

        if not context_obj.meta or "graph" not in context_obj.meta:
            graph_file = f"{context_obj.HandleRef.tag}-{context_obj.id}.rrd"
        else:
            graph_file = context_obj.meta["graph"]

        graph_path = os.path.join(settings.GRAPHS_PATH, graph_file)

        if not os.path.exists(graph_path):
            mrtg_rrd.create_rrd_file(graph_path, timestamp)

        last_update = mrtg_rrd.get_last_update_time(graph_path)

        mrtg_rrd.update_rrd(
            graph_path,
            f"{timestamp} {bps_in} {bps_out} {bps_in_max} {bps_out_max}",
            last_update,
        )

        context_obj.meta["graph"] = graph_file
        context_obj.save()

    def import_mrtg(self, data: dict):
        """
        Will import MRTG log lines into RRD and VictoriaMetrics
        """

        # RRD
        self.import_mrtg_rrd(data)

        # VictoriaMetrics
        self.import_mrtg_victoriametrics(data)

    def import_mrtg_rrd(self, data):
        """
        Import MRTG log lines into RRD file for the given context object
        """

        if not settings.GRAPHS_RRD_ENABLED:
            return

        context_obj = self.context_model.objects.get(id=data["id"])

        # check if graph file already exists

        if not context_obj.meta or "graph" not in context_obj.meta:
            graph_file = f"{context_obj.HandleRef.tag}-{context_obj.id}.rrd"
        else:
            graph_file = context_obj.meta["graph"]

        graph_path = os.path.join(settings.GRAPHS_PATH, graph_file)

        if os.path.exists(graph_path):
            os.remove(graph_path)

        log_lines = data["log_lines"]

        log_lines.reverse()

        mrtg_rrd.stream_log_lines_to_rrd(graph_path, log_lines)

        context_obj.meta["graph"] = graph_file
        context_obj.save()

    def import_mrtg_victoriametrics(self, data: dict):
        """
        Import MRTG log lines into VictoriaMetrics for the given context object

        Context object will be a virtual port or physical port instance.

        Data will be a dictionary with keys `id` and `log_lines`

        Where id is the id of the context object and log_lines is a list of strings
        as exported from MRTG.

        Each log line should be in the format:

        timestamp bps_in bps_out bps_in_max bps_out_max
        """

        if not TIMESERIES_AVAILABLE:
            return

        metrics = make_metrics()

        context_obj = self.context_model.objects.get(id=data["id"])
        members = self.members

        tags_base = {
            "ctl_org_id": self.org.remote_id,
            "ctl_ix_id": members[context_obj.port.id].ix_id,
            "ctl_org": self.org.slug,
            "ctl_port_id": data["id"],
            "ctl_device_id": context_obj.device.id,
        }

        log_lines = data["log_lines"]
        points = []
        for log_line in log_lines:
            parts = log_line.split(" ")

            if len(parts) != 5:
                log.error(f"Invalid log line: {log_line}")
                continue

            timestamp = int(parts[0])
            bps_in = float(parts[1])
            bps_out = float(parts[2])
            bps_in_max = float(parts[3])
            bps_out_max = float(parts[4])

            tags = {
                **tags_base,
            }

            point = Point(
                measurement="mrtg",
                tags=tags,
                fields={
                    "bps_in": bps_in * 8,
                    "bps_out": bps_out * 8,
                    "bps_in_max": bps_in_max * 8,
                    "bps_out_max": bps_out_max * 8,
                },
                timestamp=timestamp,
            )

            points.append(point)

        if points:
            # log.debug("Writing points to victoriametrics", points=points)
            metrics.write_many(points)


@register
class UpdateDeviceTrafficGraphs(Task):
    """
    RRD aggregation task for device traffic graphs
    """

    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_update_device_traffic_graphs"

    class TaskMeta:
        qualifiers = [
            # in order to avoid any race conditions when inserting
            # data into graphs, we limit concurrency to 1 per org
            OrgConcurrencyLimit(1),
        ]

    def run(self, *args, **kwargs):
        if not settings.GRAPHS_RRD_ENABLED:
            return

        self.aggregate_device_graphs(args)

    def aggregate_device_graphs(self, port_ids):
        """
        Aggregate the individual physical port graphs into device graphs
        """
        device_ids = set(
            models.PhysicalPort.objects.filter(id__in=port_ids).values_list(
                "device", flat=True
            )
        )

        for device_id in device_ids:
            device = models.Device.objects.get(id=device_id)
            ports = device.physical_ports.all()

            rrd_files = [
                os.path.join(settings.GRAPHS_PATH, port.meta["graph"])
                for port in ports
                if (port.meta and "graph" in port.meta)
            ]

            rrd_files = [f for f in rrd_files if os.path.exists(f)]

            output_file = f"{device.HandleRef.tag}-{device.id}.rrd"
            output_path = os.path.join(settings.GRAPHS_PATH, output_file)

            mrtg_rrd.aggregate_rrd_files(rrd_files, output_path)

            device.meta["graph"] = output_file
            device.save()


@register
class UpdateIxctlIxTrafficGraphs(Task):
    """
    RRD aggregation task for IX traffic graphs

    Will update all IX traffic graphs (ixctl)

    This will use the service bridge to query what exchange the devices belong to and then
    run a grouped aggregation accordingly.
    """

    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_update_ixctl_ix_traffic_graphs"

    class TaskMeta:
        qualifiers = [
            # in order to avoid any race conditions when inserting
            # data into graphs, we limit concurrency to 1 per org
            OrgConcurrencyLimit(1),
        ]

    def run(self, *args, **kwargs):
        if not settings.GRAPHS_RRD_ENABLED:
            return

        graph_files = self.aggregate_ix_graphs()

        RenderTrafficGraphs.create_task(*graph_files, org=self.org)

    def aggregate_ix_graphs(self):
        devices = models.Device.objects.filter(instance__org=self.org)

        ix_ports = {}

        ports = []

        for device in devices:
            ports += [vp.port.id for vp in device.virtual_ports if vp.port]

        members = ixctl.InternetExchangeMember().objects(
            ports=ports, org=self.org.remote_id
        )
        for member in members:
            ix_ports.setdefault(member.ix_id, []).append(member.port)

        graph_files = []

        for ix_id, ports in ix_ports.items():
            virtual_ports = models.VirtualPort.objects.filter(port__id__in=ports)
            rrd_files = [
                os.path.join(settings.GRAPHS_PATH, port.meta["graph"])
                for port in virtual_ports
                if (port.meta and "graph" in port.meta)
            ]

            rrd_files = [f for f in rrd_files if os.path.exists(f)]

            output_file = f"ixctl-ix-{ix_id}.rrd"
            output_path = os.path.join(settings.GRAPHS_PATH, output_file)
            try:
                mrtg_rrd.aggregate_rrd_files(rrd_files, output_path)
            except Exception:
                log.exception(f"Error aggregating rrd files for IX {ix_id}")
                continue
            graph_files.append(output_file)

        return graph_files


@register
class RenderTrafficGraphs(Task):
    """
    Takes a list of rrd files for traffic graphs and renders them into png files
    """

    periods = [
        # durartion, resolution, filename suffix
        (86400, 300, "5m"),
        (86400 * 7, 1800, "30m"),
        (86400 * 30, 7200, "2h"),
        (86400 * 365, 86400, "1d"),
    ]

    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_render_traffic_graphs"

    def run(self, *args, **kwargs):
        try:
            for obj in args:
                _, obj_type, obj_id = obj.split(".")[0].split("-")
                self.render_from_victoriametrics(obj_id, obj_type)
        except Exception as e:
            log.exception("Error rendering graphs from victoriametrics", e=e)

        try:
            if settings.GRAPHS_RRD_ENABLED:
                for graph_file in args:
                    self.render_from_rrd(graph_file)
        except Exception as e:
            log.exception("Error rendering graphs from RRD", e=e)

        self.signal_ix_traffic_processed()

    def render_from_victoriametrics(self, obj_id, obj_type):
        self.ix_graphs = {}

        metrics = make_metrics()

        object_label = None
        file_prefix = ""

        for duration, resolution, suffix in self.periods:

            # Determine object type and set parameters
            if obj_type == "virtual-port":
                obj = models.VirtualPort.objects.get(id=obj_id)
                title = f"{obj.name}"
                service = "devicectl"
                public = False
                object_label = "port"
            elif obj_type == "device":
                obj = models.Device.objects.get(id=obj_id)
                title = f"{obj.name}"
                service = "devicectl"
                public = False
                object_label = "device"
            elif obj_type == "ix":
                obj = ixctl.InternetExchange().object(obj_id)
                title = f"{obj.name}"
                service = "ixctl"
                public = True
                object_label = "ix"
                file_prefix = "ixctl-"
                self.ix_graphs.setdefault(obj_id, []).append(f"{obj_type}-{obj_id}")
            else:
                log.error(f"Unknown object type {obj_type}")
                return

            # Calculate time range
            end_time = int(time.time())
            start_time = end_time - duration

            # Query VictoriaMetrics
            if obj_type == "ix":
                result = mrtg.query_graph_ix_total(
                    org_id=self.org.remote_id,
                    ix_id=obj_id,
                    step=f"{resolution}s",
                    start=start_time,
                    end=end_time,
                )
            else:
                # TO BE IMPLEMENTED, we're currently only
                # rendering ix totals to pngs.
                continue

            # Process the data
            data = []

            # process data so its neat rows of
            # timestamp, bps_in, bps_out, bps_in_max, bps_out_max

            data_by_timestamp = {}

            for metric in result.data.result:
                metric_name = metric.metric["metric"]

                # strip mrtg_ prefix
                metric_name = metric_name.replace("mrtg_", "")

                for value in metric.values:
                    timestamp = int(value[0])
                    if timestamp not in data_by_timestamp:
                        data_by_timestamp[timestamp] = {"timestamp": timestamp}
                    data_by_timestamp[timestamp][metric_name] = float(value[1])

            data = sorted(data_by_timestamp.values(), key=lambda x: x["timestamp"])

            if not data:
                log.warning(
                    f"No valid data found for {obj_type}-{obj_id} with duration {duration}"
                )
                continue

            # Render the graph
            png_data = render_graph(
                data,
                title_label=title,
                service=service,
            )

            # Save the graph
            if default_graph_renderer() == "victoriametrics":
                image_file_name = f"{file_prefix}{obj_type}-{obj_id}-{suffix}.png"
            else:
                image_file_name = (
                    f"{file_prefix}{obj_type}-{obj_id}-{suffix}-victoria.png"
                )

            log.debug(f"VICTORIAMETRICS: {obj_type}-{obj_id} -> {image_file_name}")

            try:
                f = OrganizationFile.objects.get(org=self.org, name=image_file_name)
                f.content = png_data
                f.public = public
                f.content_type = "image/png"
                f.save()
            except OrganizationFile.DoesNotExist:
                OrganizationFile.objects.create(
                    org=self.org,
                    name=image_file_name,
                    content=png_data,
                    content_type="image/png",
                    public=public,
                )

            if public:
                self.ix_graphs.setdefault(obj_id, []).append(image_file_name)

    def render_from_rrd(self, filepath):
        self.ix_graphs = {}
        for period, resolution, suffix in self.periods:
            self._render_from_rrd(filepath, period, resolution, suffix)

    def signal_ix_traffic_processed(self):
        for ix_id, graphs in self.ix_graphs.items():
            AuditCtlIXTrafficProcessed.create_task(
                org=self.org,
                ix_id=ix_id,
                graphs=graphs,
            )

    def _render_from_rrd(self, filepath, duration, resolution, suffix):
        # get filename
        filename = os.path.basename(filepath)

        # remove extension
        filename = filename.split(".")[0]

        obj_id = filename.split("-")[-1]
        public = False

        if filename.startswith("virtual-port"):
            obj = models.VirtualPort.objects.get(id=obj_id)
            title = f"{obj.name}"
            service = "devicectl"
        elif filename.startswith("physical-port"):
            obj = models.PhysicalPort.objects.get(id=obj_id)
            title = f"{obj.name}"
            service = "devicectl"
        elif filename.startswith("device"):
            obj = models.Device.objects.get(id=obj_id)
            title = f"{obj.name}"
            service = "devicectl"

        elif filename.startswith("ixctl-ix"):
            obj = ixctl.InternetExchange().object(obj_id)
            title = f"{obj.name}"
            service = "ixctl"
            public = True
            self.ix_graphs.setdefault(obj_id, []).append(filename)

        filepath = os.path.join(settings.GRAPHS_PATH, filepath)

        png_data = render_graph(
            mrtg_rrd.load_rrd_file(filepath, duration=duration),
            title_label=title,
            service=service,
        )

        if default_graph_renderer() == "rrd":
            image_file_name = f"{filename}-{suffix}.png"
        else:
            image_file_name = f"{filename}-{suffix}-rrd.png"

        log.debug(f"RRD: {filepath} -> {image_file_name}")

        try:
            f = OrganizationFile.objects.get(org=self.org, name=image_file_name)
            f.content = png_data
            f.public = public
            f.content_type = "image/png"
            f.save()
        except OrganizationFile.DoesNotExist:
            OrganizationFile.objects.create(
                org=self.org,
                name=image_file_name,
                content=png_data,
                content_type="image/png",
                public=public,
            )


@register
class RenderSflowTrafficGraphs(Task):
    """
    Renders total IX traffic graphs from VictoriaMetrics sflow metrics to PNG files
    """

    periods = [
        # duration, resolution, filename suffix
        (86400, 300, "5m"),
        (86400 * 7, 1800, "30m"),
        (86400 * 30, 7200, "2h"),
        (86400 * 365, 86400, "1d"),
    ]

    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_render_sflow_traffic_graphs"

    def run(self, *args, **kwargs):
        ix_id = kwargs.get("ix_id")
        if not ix_id:
            raise ValueError("IX ID is required")

        ix = ixctl.InternetExchange().object(ix_id)

        for duration, resolution, suffix in self.periods:
            self.render_graph(ix, duration, resolution, suffix)

    def render_graph(self, ix, duration, resolution, suffix):
        end_time = int(time.time())
        start_time = end_time - duration

        result = sflow.query_graph_ix_total(
            org_id=self.org.remote_id,
            ix_id=ix.id,
            step=resolution,
            start=start_time,
            end=end_time,
        )

        # Process the data
        data = []
        for metric in result.data.result:
            metric_name = metric.metric["metric"]
            for value in metric.values:
                timestamp, val = value
                existing = next(
                    (item for item in data if item["timestamp"] == timestamp), None
                )
                if existing:
                    existing[metric_name] = float(val)
                else:
                    data_point = {"timestamp": int(timestamp)}
                    data_point[metric_name] = float(val)
                    data.append(data_point)

        data.sort(key=lambda x: x["timestamp"])

        # Render the graph
        png_data = render_graph(
            data,
            title_label=f"{ix.name} - Total Traffic",
            service="ixctl",
        )

        # Save the graph
        image_file_name = f"ixctl-ix-{ix.id}-{suffix}-sflow.png"

        try:
            f = OrganizationFile.objects.get(org=self.org, name=image_file_name)
            f.content = png_data
            f.public = True
            f.content_type = "image/png"
            f.save()
        except OrganizationFile.DoesNotExist:
            OrganizationFile.objects.create(
                org=self.org,
                name=image_file_name,
                content=png_data,
                content_type="image/png",
                public=True,
            )

        return image_file_name


@register
class AuditCtlIXTrafficReceived(Task):
    """
    Send event to auditctl when traffic is received on one or more
    virtual ports
    """

    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_auditctl_event_traffic_received"

    def exchanges(self):
        devices = models.Device.objects.filter(instance__org=self.org)
        ix_ports = {}
        ports = []

        for device in devices:
            ports += [vp.port.id for vp in device.virtual_ports if vp.port]

        members = ixctl.InternetExchangeMember().objects(
            ports=ports, org=self.org.remote_id
        )
        for member in members:
            ix_ports.setdefault(member.ix_id, []).append(member.port)

        for ix_id, ports in ix_ports.items():
            yield ix_id, ports

    def run(self, *args, **kwargs):
        traffic_data = kwargs.get("data")
        base_event_id = f"v0.1/{self.org.slug}/traffic/ix/"
        traffic_data_empty = True
        for ix_id, ports in self.exchanges():
            ix = ixctl.InternetExchange().object(ix_id)
            event_id = f"{base_event_id}{ix_id}/{ix.slug}/received"
            virtual_ports = [
                vp for vp in models.VirtualPort.objects.filter(port__id__in=ports)
            ]
            virtual_ports_ids = [vp.id for vp in virtual_ports]

            ix_traffic_data = [
                traffic
                for traffic in traffic_data
                if traffic["id"] in virtual_ports_ids
            ]

            if not ix_traffic_data:
                continue

            traffic_data_empty = False

            auditctl.Event().create(
                {
                    "org": self.org.slug,
                    "object_id": event_id,
                    "status": "ok",
                    "source": "devicectl",
                    "data": {
                        "components": [
                            {
                                "kind": "traffic_data",
                                "blob": json.dumps(ix_traffic_data),
                            },
                            {
                                "kind": "ix",
                                "id": ix_id,
                                "name": ix.name,
                            },
                        ]
                    },
                },
            )

            self.process_traffic_threshold_alerts(ix, virtual_ports, ix_traffic_data)

        if traffic_data_empty:
            auditctl.Event().create(
                {
                    "org": self.org.slug,
                    "object_id": event_id,
                    "status": "error",
                    "source": "devicectl",
                    "error": {
                        "message": "No data points in traffic data (empty list)",
                        "components": [],
                    },
                }
            )

    def process_traffic_threshold_alerts(
        self,
        ix: ixctl.InternetExchangeObject,
        virtual_ports: list[models.VirtualPort],
        ix_traffic_data: list[dict],
    ):
        """
        Process the traffic threshold alert notification
        for each traffic data per virtual port
        """
        ixctl_traffic_alert_config = ixctl.TrafficAlertConfig()
        traffic_alert_config_objects = list(
            ixctl_traffic_alert_config.objects(ix=ix.id)
        )

        try:
            traffic_alert_config = traffic_alert_config_objects[0]
        except IndexError:
            log.debug(f"No traffic alert config for IX {ix.id}")
            return

        if not traffic_alert_config.traffic_level:
            log.debug(f"Traffic alert config disabled for IX {ix.id}")
            return

        ixctl_member = ixctl.InternetExchangeMember()
        ixctl_traffic_alert_email = ixctl.TrafficAlertEmail()
        auditctl_event = auditctl.Event()
        aaactl_poc = aaactl.PointOfContact()
        pdbctl_ix = pdbctl.InternetExchange()
        pdbctl_network_contact = pdbctl.NetworkContact()
        peerctl_port_info = peerctl.PortInfo()
        members = list(ixctl_member.objects(ix=ix.id))

        traffic_threshold_alerts = TrafficThresholdAlerts(
            org=self.org,
            metrics=make_metrics(),
            ix=ix,
            members=members,
            traffic_alert_config=traffic_alert_config,
            member_traffic_alert_notification=MemberTrafficAlertNotification(
                org=self.org,
                ixctl_traffic_alert_email=ixctl_traffic_alert_email,
                auditctl_event=auditctl_event,
                aaactl_poc=aaactl_poc,
                ixctl_member=ixctl_member,
                ix=ix,
                pdbctl_network_contact=pdbctl_network_contact,
            ),
            operator_traffic_alert_notification=OperatorTrafficAlertNotification(
                org=self.org,
                ixctl_traffic_alert_email=ixctl_traffic_alert_email,
                auditctl_event=auditctl_event,
                aaactl_poc=aaactl_poc,
                pdbctl_ix=pdbctl_ix,
                ix=ix,
            ),
            peerctl_port_info=peerctl_port_info,
        )

        # ix traffic may contain more than one data point for the same virtual port
        # map virtual port id to most recent entry in ix_traffic_data for that
        # id

        recent_traffic_by_virtual_port = {}

        for traffic_data in ix_traffic_data:
            if not traffic_data.get("id"):
                continue

            virtual_port_id = traffic_data["id"]
            if virtual_port_id in recent_traffic_by_virtual_port:
                existing = recent_traffic_by_virtual_port[virtual_port_id]
                if existing["timestamp"] < traffic_data["timestamp"]:
                    recent_traffic_by_virtual_port[virtual_port_id] = traffic_data
            else:
                recent_traffic_by_virtual_port[traffic_data["id"]] = traffic_data

        for virtual_port in virtual_ports:
            traffic_data = recent_traffic_by_virtual_port.get(virtual_port.id)
            if not traffic_data:
                # no traffic data for this port
                continue

            if (
                virtual_port.at_capacity
                and virtual_port.at_capacity.timestamp() > traffic_data["timestamp"]
            ):
                # port was marked at capacity at a timestamp that is more recent then
                # the one we re processing
                continue

            if (
                abs(traffic_data["timestamp"] - timezone.now().timestamp())
                >= ix.traffic_poll_time
            ):
                # we only want to process the timestamp that matches the current
                # time with a window defined by the traffic poll time (so for example now +- 5 minutes)
                continue

            log.debug(
                f"Processing traffic threshold alerts for {virtual_port.id}: {traffic_data}"
            )

            traffic_threshold_alerts.process_traffic_threshold_alerts(
                virtual_port=virtual_port,
                traffic=traffic_data.get("bps_in") * 8,
            )

            traffic_threshold_alerts.process_traffic_threshold_alerts(
                virtual_port=virtual_port,
                traffic=traffic_data.get("bps_out") * 8,
            )


@register
class AuditCtlIXTrafficProcessed(Task):
    """
    Send event to auditctl when traffic is processed on one or more
    virtual ports
    """

    event_type = "processed"

    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_auditctl_event_traffic_processed"

    def run(self, *args, **kwargs):
        ix_id = kwargs.get("ix_id")
        ix = ixctl.InternetExchange().object(ix_id)
        base_event_id = f"v0.1/{self.org.slug}/traffic/ix/"
        event_id = f"{base_event_id}{ix_id}/{ix.slug}/processed"
        graphs = kwargs.get("graphs")

        if not graphs:
            auditctl.Event().create(
                {
                    "org": self.org.slug,
                    "object_id": event_id,
                    "status": "error",
                    "source": "devicectl",
                    "error": {
                        "message": "No graphs updated",
                        "components": [
                            {
                                "kind": "ix",
                                "id": ix_id,
                                "name": ix.name,
                            }
                        ],
                    },
                }
            )
            return

        auditctl.Event().create(
            {
                "org": self.org.slug,
                "object_id": event_id,
                "status": "ok",
                "source": "devicectl",
                "data": {
                    "components": [
                        {
                            "kind": "ix",
                            "id": ix_id,
                            "name": ix.name,
                        },
                        {
                            "kind": "graphs",
                            "blob": json.dumps(graphs),
                        },
                    ]
                },
            },
        )


class TrafficAlertNotificationBase:
    """
    Traffic Alert Notification Base
    """

    def __init__(
        self,
        org,
        ixctl_traffic_alert_email: ixctl.TrafficAlertEmail,
        auditctl_event: auditctl.Event,
        aaactl_poc: aaactl.PointOfContact,
        ix: ixctl.InternetExchangeObject,
    ):
        self.org = org
        self.aaactl_poc = aaactl_poc
        self.ixctl_traffic_alert_email = ixctl_traffic_alert_email
        self.auditctl_event = auditctl_event
        self.ix = ix

    @property
    def alert_email_type(self) -> str:
        """
        The email type for the email notification i.e. 'traffic_alert_ix', 'traffic_alert_net'
        Used to get the email type
        """
        raise NotImplementedError("Subclasses must set the alert email type.")

    @property
    def alert_service_type(self) -> str:
        """
        The service type for the notification i.e. 'ixctl', 'peerctl'
        """
        raise NotImplementedError("Subclasses must set the alert service type.")

    def get_pdb_email_notification_recepients(
        self, virtual_port: models.VirtualPort
    ) -> list[str] | None:
        """
        Gets the email recipients from pdb
        """
        raise NotImplementedError(
            "Subclasses must implement the 'get_pdb_email_notification_recepients' method."
        )

    def get_poc_email_notification_recepients(
        self, member: ixctl.InternetExchangeMemberObject
    ) -> list[str] | None:
        """
        Gets the email recipients from aaactl point of contact
        """
        raise NotImplementedError(
            "Subclasses must implement the 'get_poc_email_notification_recepients' method."
        )

    def send_notification(
        self,
        notification_type: str,
        recipients: list[str],
        member: ixctl.InternetExchangeMemberObject,
    ) -> None:
        """
        Sends the notification depending on the notification type
        """
        if notification_type == "email":
            traffic_alert_email = self.get_traffic_alert_email(member)
            if not traffic_alert_email:
                log.warning(
                    f"Unable to obtain suitable contact point for IX operator traffic alerts. ({self.ix.name} #{self.ix.id})"
                )
                return
            self.send_email(recipients, traffic_alert_email)

    def get_traffic_alert_email(self, member: ixctl.InternetExchangeMemberObject):
        """
        Gets the traffic alert email from ixctl
        """
        return self.ixctl_traffic_alert_email.get_traffic_alert_email(
            ix_id=self.ix.id, email_type=self.alert_email_type, member_id=member.id
        )

    def send_email(
        self, recipients: list[str], traffic_alert_emails: ixctl.TrafficAlertEmailObject
    ) -> None:
        """
        Sends an email via auditctl
        """

        for traffic_alert_email in traffic_alert_emails:
            self.auditctl_event.send_email(
                org_slug=self.org.slug,
                source_service_tag="devicectl",
                category="traffic_alert",
                subject=traffic_alert_email["subject"],
                message=traffic_alert_email["message"],
                recipients=recipients,
            )

    def get_recipients(
        self,
        virtual_port: models.VirtualPort,
        member: ixctl.InternetExchangeMemberObject,
    ) -> list[str] | None:
        """
        Gets the nofication recipients first from the aaactl poc
        if not found then gets it from pdb
        """
        recipients = self.get_poc_email_notification_recepients(member, virtual_port)
        if not recipients:
            recipients = self.get_pdb_email_notification_recepients(
                member, virtual_port
            )
        return recipients

    def process_notification(
        self,
        virtual_port: models.VirtualPort,
        member: ixctl.InternetExchangeMemberObject,
    ) -> None:
        """
        This is the main method that processes the notification
        Functions include
            - getting the recipients
            - sending the notification
            - updating the notification fields of the virtual ports
        """
        recipients = self.get_recipients(virtual_port=virtual_port, member=member)
        if not recipients:
            log.warning(
                f"No recipients in traffic alert contact point for IX. ({self.ix.name} #{self.ix.id})"
            )
            return
        self.send_notification(
            notification_type="email", recipients=recipients, member=member
        )


class OperatorTrafficAlertNotification(TrafficAlertNotificationBase):
    """
    Sends Traffic Alert Notification for IX Operators
    """

    def __init__(
        self,
        org,
        ixctl_traffic_alert_email: ixctl.TrafficAlertEmail,
        auditctl_event: auditctl.Event,
        aaactl_poc: aaactl.PointOfContact,
        pdbctl_ix: pdbctl.InternetExchange,
        ix: ixctl.InternetExchangeObject,
    ):
        super().__init__(
            org=org,
            ixctl_traffic_alert_email=ixctl_traffic_alert_email,
            auditctl_event=auditctl_event,
            aaactl_poc=aaactl_poc,
            ix=ix,
        )
        self.pdbctl_ix = pdbctl_ix

    @property
    def alert_email_type(self) -> str:
        return "traffic_alert_ix"

    @property
    def alert_service_type(self) -> str:
        return "ixctl"

    def get_pdb_email_notification_recepients(
        self,
        member: ixctl.InternetExchangeMemberObject,
        virtual_port: models.VirtualPort,
    ) -> list[str] | None:
        data = self.pdbctl_ix.object(id=self.ix.pdb_id)
        if not data:
            log.debug(f"No recepient found in pdb for IX {self.ix.id}.")
            return
        return [data.tech_email] if data.tech_email else None

    def get_poc_email_notification_recepients(
        self,
        member: ixctl.InternetExchangeMemberObject,
        virtual_port: models.VirtualPort,
    ) -> list[str] | None:
        try:
            poc = list(
                self.aaactl_poc.objects(
                    org=self.org.slug,
                    type="notifications",
                    delivery_type="email",
                    status="ok",
                    service=self.alert_service_type,
                )
            )[0]
        except IndexError:
            return

        for config in poc.config:
            if config.get("service") == self.alert_service_type:
                return config.get("recipients")
        return


class MemberTrafficAlertNotification(TrafficAlertNotificationBase):
    """
    Sends Traffic Alert Notification for IX Members
    """

    def __init__(
        self,
        org,
        ixctl_traffic_alert_email: ixctl.TrafficAlertEmail,
        auditctl_event: auditctl.Event,
        aaactl_poc: aaactl.PointOfContact,
        ixctl_member: ixctl.InternetExchangeMember,
        ix: ixctl.InternetExchangeObject,
        pdbctl_network_contact: pdbctl.NetworkContact,
    ):
        super().__init__(
            org=org,
            ixctl_traffic_alert_email=ixctl_traffic_alert_email,
            auditctl_event=auditctl_event,
            aaactl_poc=aaactl_poc,
            ix=ix,
        )
        self.ixctl_member = ixctl_member
        self.pdbctl_network_contact = pdbctl_network_contact

    @property
    def alert_email_type(self) -> str:
        return "traffic_alert_net"

    @property
    def alert_service_type(self) -> str:
        return "peerctl"

    def get_pdb_email_notification_recepients(
        self,
        member: ixctl.InternetExchangeMemberObject,
        virtual_port: models.VirtualPort,
    ) -> list[str] | None:
        recipients = None
        try:
            network_contacts = self.pdbctl_network_contact.objects(asn=member.asn)
            for network_contact in network_contacts:
                if network_contact.role == "Technical":
                    return [network_contact.email]
        except IndexError:
            log.debug(f"No recepient found in pdb for member: {member.id}.")
        return recipients

    def get_poc_email_notification_recepients(
        self,
        member: ixctl.InternetExchangeMemberObject,
        virtual_port: models.VirtualPort,
    ) -> list[str] | None:
        try:
            poc = list(
                self.aaactl_poc.objects(
                    type="notifications",
                    delivery_type="email",
                    status="ok",
                    service=self.alert_service_type,
                    entity=member.asn,
                )
            )[0]
        except IndexError:
            return

        for config in poc.config:
            if (
                config.get("service") == self.alert_service_type
                and config.get("entity") == member.asn
            ):
                return config.get("recipients")
        return


class TrafficThresholdAlerts:
    """
    Handles Traffic Threshold Alerts
    `process_traffic_threshold_alerts` being the main function
    """

    def __init__(
        self,
        org,
        metrics: Metrics,
        ix: ixctl.InternetExchangeObject,
        members: list[ixctl.InternetExchangeMemberObject],
        traffic_alert_config: ixctl.TrafficAlertConfigObject,
        member_traffic_alert_notification: MemberTrafficAlertNotification,
        operator_traffic_alert_notification: OperatorTrafficAlertNotification,
        peerctl_port_info: peerctl.PortInfo,
    ):
        self.org = org
        self.metrics = metrics
        self.member_traffic_alert_notification = member_traffic_alert_notification
        self.operator_traffic_alert_notification = operator_traffic_alert_notification
        self.ix = ix
        self.peerctl_port_info = peerctl_port_info
        self.members = members
        self.traffic_alert_config = traffic_alert_config
        self.members_by_port = {
            member.port: member for member in self.members if member.port
        }

    def process_traffic_threshold_alerts(
        self, virtual_port: models.VirtualPort, traffic: int
    ) -> None:
        """
        This is the main method that processes the traffic threshold alerts
            - Gets traffic alert config and uses that to process the alert
            - Calculates the threshold and determines whether to send a notification

        Traffic is exepcted to be in bits per second
        """

        member = self.members_by_port.get(virtual_port.port.id)
        port_bandwidth = member.speed * 1_000_000

        threshold_bandwidth = (
            self.traffic_alert_config.traffic_level / 100
        ) * port_bandwidth
        counter_threshold = self.traffic_alert_config.time_period / (
            self.ix.traffic_poll_time // 60
        )

        log.debug(
            "Processing traffic threshold alerts",
            virtual_port=virtual_port,
            port_bandwidth=port_bandwidth,
            threshold_bandwidth=threshold_bandwidth,
            counter_threshold=counter_threshold,
            traffic=traffic,
        )

        if traffic > threshold_bandwidth:
            virtual_port.capacity_alert += 1
            virtual_port.save()
            self.log_traffic_stats_to_time_series(
                virtual_port=virtual_port, at_capacity=1
            )

        elif traffic < threshold_bandwidth and virtual_port.capacity_alert != 0:
            virtual_port.capacity_alert = 0
            virtual_port.save()
            self.log_traffic_stats_to_time_series(
                virtual_port=virtual_port, at_capacity=0
            )

        if virtual_port.capacity_alert >= counter_threshold:
            virtual_port.at_capacity = timezone.now()
            virtual_port.save()
            self.send_traffic_alert_notification(virtual_port)

    def send_traffic_alert_notification(self, virtual_port: models.VirtualPort) -> None:
        """
        Sends traffic alert notification
        Checks for both operator and member notifications
        """
        member = self.members_by_port.get(virtual_port.port.id)

        if not member:
            log.warning(f"No member found for virtual port {virtual_port.id}")
            return

        if self.traffic_alert_config.operator_emails and self.can_send_ix_notification(
            virtual_port=virtual_port
        ):
            self.operator_traffic_alert_notification.process_notification(
                virtual_port=virtual_port,
                member=member,
            )
            virtual_port.capacity_notified_ix = timezone.now()
            virtual_port.save()

        if (
            self.traffic_alert_config.member_emails
            and self.can_send_member_notification(virtual_port=virtual_port)
        ):

            if not self.member_activated_threshold_alerts(member):
                log.info(
                    f"Member {member.id} has not activated threshold alerts - skipping"
                )
                return

            self.member_traffic_alert_notification.process_notification(
                virtual_port=virtual_port,
                member=member,
            )
            virtual_port.capacity_notified_net = timezone.now()
            virtual_port.save()

    def can_send_ix_notification(self, virtual_port: models.VirtualPort):
        if not virtual_port.capacity_notified_ix:
            return True

        next_alert_time = virtual_port.capacity_notified_ix + timedelta(
            days=self.traffic_alert_config.operator_emails_max_frequency
        )
        return timezone.now() >= next_alert_time

    def can_send_member_notification(self, virtual_port: models.VirtualPort):
        if not virtual_port.capacity_notified_net:
            return True

        next_alert_time = virtual_port.capacity_notified_net + timedelta(
            days=self.traffic_alert_config.operator_emails_max_frequency
        )
        return timezone.now() >= next_alert_time

    def member_activated_threshold_alerts(
        self, member: ixctl.InternetExchangeMemberObject
    ):
        """
        Checks that the member has activated a threshold notification alert
        """
        port_info_objects = list(
            self.peerctl_port_info.objects(ref_id=f"ixctl:{member.id}")
        )
        if not port_info_objects:
            return False
        return port_info_objects[0].traffic_threshold_alert

    def log_traffic_stats_to_time_series(
        self, virtual_port: models.VirtualPort, at_capacity: int
    ) -> None:
        """
        Logs the traffic stats to time series db
        """
        self.metrics.write(
            measurement="traffic_stats",
            tags={
                "ctl_org_id": self.org.remote_id,
                "ctl_org": self.org.slug,
                "ctl_port_id": virtual_port.id,
                "ctl_ix_id": self.ix.id,
                "ctl_device_id": virtual_port.device.id,
            },
            fields={
                "at_capacity": at_capacity,
            },
            timestamp=timezone.now().timestamp(),
        )
