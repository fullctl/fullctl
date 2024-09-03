import json
import os
import time

import structlog

import fullctl.django.tasks.qualifiers as qualifiers
import fullctl.graph.mrtg.rrd as mrtg_rrd
import fullctl.service_bridge.auditctl as auditctl
import fullctl.service_bridge.ixctl as ixctl
import fullctl.service_bridge.nautobot as nautobot
import fullctl.service_bridge.peerctl as peerctl
from django.conf import settings
from fullctl.django.models import Task
from fullctl.django.models.concrete import OrganizationFile
from fullctl.django.tasks import register
from fullctl.graph.render.traffic import render_graph
from fullctl.metrics import Metrics
from fullctl.metrics.schema import Point

import django_devicectl.sflow as sflow
import django_devicectl.models.devicectl as models

log = structlog.get_logger("django_structlog")

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

        if self.context_model == models.PhysicalPort:
            UpdateDeviceTrafficGraphs.create_task(
                org=self.org,
                *processed_port_ids,
            )
        else:
            AuditCtlIXTrafficReceived.create_task(
                org=self.org,
                data=kwargs.get("update", []),
            )
            UpdateIxctlIxTrafficGraphs.create_task(
                org=self.org,
            )

    def update_victoriametrics(self, all_data:list[dict]):

        if not all_data:
            return

        metrics = Metrics(
            settings.TIMESERIES_DB_URL,
            (settings.TIMESERIES_DB_USER, settings.TIMESERIES_DB_PASSWORD) if settings.TIMESERIES_DB_USER else None
        )

        tags_base = {
            "ctl_org_id": self.org.remote_id,
            "ctl_org": self.org.slug,
        }

        port_ids = []
        for data in all_data:
            virtual_port = self.context_model.objects.get(id=data["id"])
            port_ids.append(virtual_port.port.id)

        members = {m.port: m for m in ixctl.InternetExchangeMember().objects(ports=port_ids, org=self.org.remote_id)}


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

    def import_mrtg(self, data):
        """
        Import MRTG log lines into RRD file for the given context object
        """

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

        for log_line in log_lines:
            print(log_line)

        mrtg_rrd.stream_log_lines_to_rrd(graph_path, log_lines)

        context_obj.meta["graph"] = graph_file
        context_obj.save()


@register
class UpdateDeviceTrafficGraphs(Task):
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
        for obj in args:
            _, obj_type, obj_id = obj.split(".")[0].split('-')
            self.render_from_victoriametrics(obj_id, obj_type)

        for graph_file in args:
            self.render_from_rrd(graph_file)

    def render_from_victoriametrics(self, obj_id, obj_type):
        self.ix_graphs = {}

        metrics = Metrics(
            settings.TIMESERIES_DB_URL,
            (settings.TIMESERIES_DB_USER, settings.TIMESERIES_DB_PASSWORD) if settings.TIMESERIES_DB_USER else None
        )

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
            query = metrics.build_query_string(
                aggregator=None,
                metrics=["mrtg_bps_in", "mrtg_bps_out", "mrtg_bps_in_max", "mrtg_bps_out_max"],
                tags={
                    f"ctl_{object_label}_id": obj_id,
                    "ctl_org": self.org.slug,
                },
                time_range=resolution,
            )

            query = f"sum by (__name__) ({query})"

            result = metrics.query_range(query, start=str(start_time), end=str(end_time), step=str(resolution)+"s")

            # Process the data
            data = []
                        
            # process data so its neat rows of
            # timestamp, bps_in, bps_out, bps_in_max, bps_out_max

            data_by_timestamp = {}

            for metric in result.data.result:
                metric_name = metric.metric["__name__"]

                # strip mrtg_ prefix
                metric_name = metric_name.replace("mrtg_", "")

                for value in metric.values:
                    timestamp = int(value[0])
                    if timestamp not in data_by_timestamp:
                        data_by_timestamp[timestamp] = {"timestamp": timestamp}
                    data_by_timestamp[timestamp][metric_name] = float(value[1])

            data = sorted(data_by_timestamp.values(), key=lambda x: x["timestamp"])

            if not data:
                log.warning(f"No valid data found for {obj_type}-{obj_id} with duration {duration}")
                continue

            # Render the graph
            png_data = render_graph(
                data,
                title_label=title,
                service=service,
            )

            # Save the graph
            image_file_name = f"{file_prefix}{obj_type}-{obj_id}-{suffix}-victoria.png"

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

        # Process IX graphs if any
        for ix_id, graphs in self.ix_graphs.items():
            AuditCtlIXTrafficProcessed.create_task(
                org=self.org,
                ix_id=ix_id,
                graphs=graphs,
            )

    def render_from_rrd(self, filepath):
        self.ix_graphs = {}
        for period, resolution, suffix in self.periods:
            self._render_from_rrd(filepath, period, resolution, suffix)

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

        image_file_name = f"{filename}-{suffix}.png"

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
        ix_id = kwargs.get('ix_id')
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
            end=end_time
        )

        # Process the data
        data = []
        for metric in result.data.result:
            metric_name = metric.metric['metric']
            for value in metric.values:
                timestamp, val = value
                existing = next((item for item in data if item['timestamp'] == timestamp), None)
                if existing:
                    existing[metric_name] = float(val)
                else:
                    data_point = {'timestamp': int(timestamp)}
                    data_point[metric_name] = float(val)
                    data.append(data_point)

        data.sort(key=lambda x: x['timestamp'])

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
        for ix_id, ports in self.exchanges():
            ix = ixctl.InternetExchange().object(ix_id)
            event_id = f"{base_event_id}{ix_id}/{ix.slug}/received"
            virtual_ports = [
                vp.id for vp in models.VirtualPort.objects.filter(port__id__in=ports)
            ]

            ix_traffic_data = [
                traffic for traffic in traffic_data if traffic["id"] in virtual_ports
            ]

            if not ix_traffic_data:
                auditctl.Event().create(
                    {
                        "org": self.org.slug,
                        "object_id": event_id,
                        "status": "error",
                        "source": "devicectl",
                        "error": {
                            "message": "No data points in traffic data (empty list)",
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
                continue

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
