import os
from typing import List

import fullctl.service_bridge.ixctl as ixctl
import rrdtool
from django.conf import settings
from fullctl.django.management.commands.base import CommandInterface
from fullctl.metrics import Metrics
from fullctl.metrics.schema import Point

from django_devicectl.models.devicectl import VirtualPort


class Command(CommandInterface):
    help = "Import MRTG RRD data to VictoriaMetrics for specified organization"

    def add_arguments(self, parser):
        super().add_arguments(parser)

        # add argument to ignore `migrated` status and re-import all ports

        parser.add_argument(
            "--force",
            action="store_true",
            help="Force re-import of all ports. (Will remove existing VM MRTG metrics for the port)",
        )

    def run(self, *args, **kwargs):
        metrics = Metrics(
            settings.TIMESERIES_DB_URL,
            (settings.TIMESERIES_DB_USER, settings.TIMESERIES_DB_PASSWORD)
            if settings.TIMESERIES_DB_USER
            else None,
        )

        force = kwargs.get("force", False)

        for virtual_port in self.find_ports_with_graphs():

            if virtual_port.meta.get("migrated"):
                if not force:
                    self.log_info(
                        f"Skipping port {virtual_port.id} as it has already been migrated"
                    )
                    continue
                else:
                    self.log_info(
                        f"Port {virtual_port.id} has already been migrated, but force flag is set. Re-importing. Existing VM metrics for the port will be deleted."
                    )
                    metrics.delete(
                        f'{{__name__=~"mrtg_*", ctl_port_id="{virtual_port.id}"}}'
                    )

            member = ixctl.InternetExchangeMember().first(ports=[virtual_port.port.id])

            if member is None:
                self.log_info(
                    f"Could not find member for port PORT {virtual_port.port.id} VIRTUAL {virtual_port.id}"
                )
                continue

            self.log_info(f"Processing port {virtual_port.id} for IX {member.ix_id}")

            if not virtual_port.device:
                self.log_info(f"Port {virtual_port.id} has no device. Skipping.")
                continue

            if not self.commit:
                continue

            rrd_file = os.path.join(settings.GRAPHS_PATH, virtual_port.meta["graph"])

            self.import_mrtg_rrd_to_victoriametrics(
                metrics=metrics,
                rrd_files=[rrd_file],
                tags={
                    "ctl_org_id": virtual_port.device.org.remote_id,
                    "ctl_org": virtual_port.device.org.slug,
                    "ctl_device_id": virtual_port.device.id,
                    "ctl_port_id": virtual_port.id,
                    "ctl_ix_id": member.ix_id,
                },
            )

            virtual_port.meta["migrated"] = True
            virtual_port.save()

    def find_ports_with_graphs(self) -> List[VirtualPort]:
        qset = VirtualPort.objects.filter(meta__graph__isnull=False)
        return qset

    def get_rra_info(self, rrd_file: str) -> List[tuple]:
        """Get information about RRAs in the RRD file."""
        info = rrdtool.info(rrd_file)
        rras = []
        i = 0
        while f"rra[{i}].cf" in info:
            rras.append(
                (info[f"rra[{i}].pdp_per_row"] * info["step"], info[f"rra[{i}].rows"])
            )
            i += 1
        return sorted(rras, key=lambda x: x[0])  # Sort by step

    def import_mrtg_rrd_to_victoriametrics(
        self, metrics: Metrics, rrd_files: List[str], tags: dict, batch_size: int = 1000
    ):
        """
        Import all data from MRTG RRD files into VictoriaMetrics, maintaining original resolution.
        """
        measurement = "mrtg"
        points = []

        for rrd_file in rrd_files:
            try:
                info = rrdtool.info(rrd_file)
            except rrdtool.OperationalError:
                self.log_error(f"Error reading RRD file {rrd_file}. Skipping.")
                continue

            last_update = info["last_update"]
            rras = self.get_rra_info(rrd_file)

            for step, rows in rras:
                start_time = last_update - step * rows
                end_time = last_update

                # Fetch data for this RRA
                try:
                    rrd_data = rrdtool.fetch(
                        rrd_file,
                        "AVERAGE",
                        "-r",
                        str(step),
                        "-s",
                        str(start_time),
                        "-e",
                        str(end_time),
                    )
                except rrdtool.OperationalError:
                    self.log_info(
                        f"Error fetching data for {rrd_file} with step {step}. Skipping this RRA."
                    )
                    continue

                time_index, column_names, values = rrd_data
                fetch_start, fetch_end, fetch_step = time_index

                timestamp = fetch_start
                for row in values:
                    fields = {}
                    for i, value in enumerate(row):
                        if i < len(column_names):
                            fields[column_names[i]] = value

                    # Remove None values
                    fields = {k: v for k, v in fields.items() if v is not None}

                    if fields:  # Only create a point if there are non-None values
                        point = Point(
                            measurement=measurement,
                            tags=tags,
                            fields=fields,
                            timestamp=timestamp,
                        )
                        points.append(point)

                        if len(points) >= batch_size:
                            metrics.write_many(points)
                            points = []

                    timestamp += fetch_step

        # Write any remaining points
        if points:
            metrics.write_many(points)
            self.log_info(
                f"Imported data from {len(rrd_files)} RRD files into VictoriaMetrics, maintaining original resolution."
            )
