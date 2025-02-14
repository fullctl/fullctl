from django.conf import settings
from fullctl.metrics import Metrics
from fullctl.metrics.schema import QueryResult

METRIC_TAGS = [
    "org",
    "org_id",
    "ix_id",
    "port_id",
    "device_id",
]

METRIC_FIELDS = ["bps_in", "bps_in_max", "bps_out", "bps_out_max"]

LABEL_PREFIX = "ctl_"

TRAFFIC_GRAPH_QUERY_BASE = """
sum by (metric) (
    label_replace(
        sum(mrtg_bps_in{{{tags_in}}}) or vector(0),
        "metric", "bps_in", "", ""
    )
) or
sum by (metric) (
    label_replace(
        sum(mrtg_bps_out{{{tags_out}}}) or vector(0),
        "metric", "bps_out", "", ""
    )
) or
max by (metric) (
    label_replace(
        sum(mrtg_bps_in_max{{{tags_in}}}) or vector(0),
        "metric", "bps_in_max", "", ""
    )
) or
max by (metric) (
    label_replace(
        sum(mrtg_bps_out_max{{{tags_out}}}) or vector(0),
        "metric", "bps_out_max", "", ""
    )
)
"""

def metrics_client() -> Metrics:
    return Metrics(
        settings.TIMESERIES_DB_URL,
        (
            (settings.TIMESERIES_DB_USER, settings.TIMESERIES_DB_PASSWORD)
            if settings.TIMESERIES_DB_USER
            else None
        ),
    )


def query_graph_ix_total(
    org_id: int,
    ix_id: int,
    step: str,
    start: str | int,
    end: str | int | None = None,
    **kwargs,
) -> QueryResult:
    """
    Queries bits per second for a specific IX (in and out)

    Arguments:

    - org_id: Organization ID (aaactl ID)
    - ix_id: IX ID
    - step: tick size (e.g. 15m)
    - start: start time (unix timestamp or relative time like -1h)
    - end: end time (unix timestamp or relative time like -1h)
    """

    metrics = metrics_client()

    # Construct victoria metrics query

    # aggregate by tag `ctl_ix_id`
    # - sum of `mrtg_bps_in` and `mrtg_bps_out`
    # - max of `mrtg_bps_in_max` and `mrtg_bps_out_max`
    # return 4 series

    tags = f'ctl_org_id="{org_id}", ctl_ix_id="{ix_id}"'

    query = TRAFFIC_GRAPH_QUERY_BASE.format(tags_in=tags, tags_out=tags, step=step)

    return metrics.query_range(query, start=start, end=end, step=step)


def query_graph_port_total(
    org_id: int, port_id: int, step: str, start: str, end: str, **kwargs
) -> QueryResult:
    """
    Queries bits per second for a specific port (in and out)

    This is done by looking for a match in `ctl_port_id_src` for outgoing
    traffic and `ctl_port_id_dst` for incoming traffic.

    Arguments:

    - org_id: Organization ID (aaactl ID)
    - port_id: Port ID
    - step: tick size (e.g. 15m)
    - start: start time (unix timestamp or relative time like -1h)
    - end: end time (unix timestamp or relative time like -1h)
    """

    metrics = metrics_client()

    tags_in = f'ctl_org_id="{org_id}", ctl_port_id="{port_id}"'
    tags_out = f'ctl_org_id="{org_id}", ctl_port_id="{port_id}"'

    query = TRAFFIC_GRAPH_QUERY_BASE.format(
        tags_in=tags_in, tags_out=tags_out, step=step
    )
    return metrics.query_range(query, start=start, end=end, step=step)
