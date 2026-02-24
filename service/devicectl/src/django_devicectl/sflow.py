from django.conf import settings

from fullctl.metrics import Metrics
from fullctl.metrics.schema import QueryResult

__all__ = [
    "save",
    "query_graph_ix_total",
    "query_graph_port_total",
    "query_graph_asn",
    "query_graph_asn_pair",
    "asn_table",
]

METRIC_TAGS = [
    "org",
    "org_id",
    "ix_id",
    "asn_src",
    "asn_dst",
    "port_id_src",
    "port_id_dst",
    "device_id_src",
    "device_id_dst",
    "mac_src",
    "mac_dst",
]

METRIC_FIELDS = ["bytes", "packets"]

LABEL_PREFIX = "ctl_"


def metrics_client() -> Metrics:
    return Metrics(
        settings.TIMESERIES_DB_URL,
        (
            (settings.TIMESERIES_DB_USER, settings.TIMESERIES_DB_PASSWORD)
            if settings.TIMESERIES_DB_USER
            else None
        ),
    )


def keys_to_tags(data: dict) -> dict:
    return {f"{LABEL_PREFIX}{k}": v for k, v in data.items()}


def save(data: list[dict]):
    """
    Save sflow data to timeseries database

    This assumes already validated data through
    rest.serializers.sflow.SflowData
    """
    metrics = Metrics(settings.TIMESERIES_DB_URL)
    metrics.write_many(
        [
            {
                "measurement": "sflow",
                "tags": {
                    "service": "devicectl",
                    **{f"{LABEL_PREFIX}{k}": sflow_data[k] for k in METRIC_TAGS},
                },
                "fields": {k: sflow_data[k] for k in METRIC_FIELDS},
                "timestamp": int(sflow_data["timestamp"]),
            }
            for sflow_data in data
        ]
    )


def step_size_for_max(step: int) -> int:
    """
    Takes step as seconds and returns a faster step size
    to query for max values
    """

    if step < 86400:
        return 300
    elif step < 86400 * 30:
        return 3600
    else:
        return 86400


def validate_query_params(**kwargs):
    """
    Validate query parameters against tags
    """
    for k in kwargs:
        if k not in METRIC_TAGS:
            raise ValueError(f"Invalid query parameter: {k}")


# The basic query for traffic data
#
# We use `or vector(0)` to ensure that we always get timeseries data
# for the full duration. If there is no data, we will get a 0 value.
#
# We use `label_replace` to ensure sane metric names in the result
#
# `bps_in`, `bps_out` are the average bits per second for incoming and outgoing traffic in the given time range
# `bps_in_max`, `bps_out_max` are the maximum bits per second for incoming and outgoing traffic in the given time range

TRAFFIC_GRAPH = """
label_replace(
    (sum(avg_over_time(sflow_bytes{{{tags_in}}})) * 8 / {collection_step}) or vector(0),
    "metric", "bps_in", "", ""
)
or
label_replace(
    max(sum(max_over_time(sflow_bytes{{{tags_in}}})) * 8 / {collection_step}) or vector(0),
    "metric", "bps_in_max", "", ""
)
or
label_replace(
    (sum(avg_over_time(sflow_bytes{{{tags_out}}})) * 8 / {collection_step}) or vector(0),
    "metric", "bps_out", "", ""
)
or
label_replace(
    max(sum(max_over_time(sflow_bytes{{{tags_out}}})) * 8 / {collection_step}) or vector(0),
    "metric", "bps_out_max", "", ""
)
"""


def query_graph_ix_total(
    org_id: int,
    ix_id: int,
    step: str,
    start: str | int,
    end: str | int | None = None,
    collection_step: int = 300,
    **kwargs,
) -> QueryResult:
    """
    Queries bits per second for a specific IX (in and out)

    Creates 4 metrics:

    - bps_in (avg of all incoming traffic as bits per second)
    - bps_out (avg of all outgoing traffic as bits per second)
    - bps_in_max (max of all incoming traffic as bits per second)
    - bps_out_max (max of all outgoing traffic as bits per second)

    Arguments:

    - org_id: Organization ID (aaactl ID) - the organization that stores the data
    - ix_id: IX ID
    - step: tick size (e.g. 15m)
    - start: start time (unix timestamp or relative time like -1h)
    - end: end time (unix timestamp or relative time like -1h)
    - collection_step: step size for the collection (default 300) - this should be the interval at which data is collected
    """

    metrics = metrics_client()

    # Construct the main query
    tags_in = f'ctl_org_id="{org_id}", ctl_ix_id="{ix_id}", ctl_port_id_dst!=""'
    tags_out = f'ctl_org_id="{org_id}", ctl_ix_id="{ix_id}", ctl_port_id_src!=""'

    step = int(step) if isinstance(step, str) else step

    query = TRAFFIC_GRAPH.format(
        tags_in=tags_in,
        tags_out=tags_out,
        step=step,
        step_max=step_size_for_max(step),
        collection_step=collection_step,
    )

    return metrics.query_range(
        query, start=start, end=end, step=step, keep_metric_names=True
    )


def query_graph_port_total(
    org_id: int,
    port_id: int,
    step: str,
    start: str,
    end: str,
    collection_step: int = 300,
    **kwargs,
) -> QueryResult:
    """
    Queries bits per second for a specific port (in and out)

    This is done by looking for a match in `ctl_port_id_src` for outgoing
    traffic and `ctl_port_id_dst` for incoming traffic.

    Creates 4 metrics:

    - bps_in (avg of all incoming traffic as bits per second)
    - bps_out (avg of all outgoing traffic as bits per second)
    - bps_in_max (max of all incoming traffic as bits per second)
    - bps_out_max (max of all outgoing traffic as bits per second)

    Arguments:

    - org_id: Organization ID (aaactl ID) - the organization that stores the data
    - port_id: Port ID
    - step: tick size (e.g. 15m)
    - start: start time (unix timestamp or relative time like -1h)
    - end: end time (unix timestamp or relative time like -1h)
    - query_override: Override the query with a custom query (useful for testing and debugging)
    - collection_step: step size for the collection (default 300) - this should be the interval at which data is collected
    """

    metrics = metrics_client()

    tags_in = f'ctl_org_id="{org_id}", ctl_port_id_dst="{port_id}"'
    tags_out = f'ctl_org_id="{org_id}", ctl_port_id_src="{port_id}"'

    step = int(step) if isinstance(step, str) else step

    query_override = kwargs.pop("query_override", None)

    query_base = query_override or TRAFFIC_GRAPH

    query = query_base.format(
        tags_in=tags_in,
        tags_out=tags_out,
        step=step,
        step_max=step_size_for_max(step),
        collection_step=collection_step,
    )

    return metrics.query_range(query, start=start, end=end, step=step)


def query_graph_asn(
    org_id: int,
    port_id: int,
    asn: int,
    step: str,
    start: str,
    end: str,
    collection_step: int = 300,
    **kwargs,
) -> QueryResult:
    """
    Queries bits per second for a specific ASN to ASN (in and out)

    This is done by looking for a match in `ctl_asn_src` for outgoing
    traffic and `ctl_asn_dst` for incoming traffic.

    This needs to aggregate to individual ASNs, not just the total.

    In the end we want to have a graph that shows individual metrics for each ASN that has traffic to/from the given ASN.

    Creates 4 metrics (per asn):

    - bps_in (avg of all incoming traffic as bits per second)
    - bps_out (avg of all outgoing traffic as bits per second)
    - bps_in_max (max of all incoming traffic as bits per second)
    - bps_out_max (max of all outgoing traffic as bits per second)

    Arguments:

    - org_id: Organization ID (aaactl ID) - the organization that stores the data
    - port_id: Port ID - needs to be the port for the source ASN
    - asn: ASN
    - step: tick size (e.g. 15m)
    - start: start time (unix timestamp or relative time like -1h)
    - end: end time (unix timestamp or relative time like -1h)
    - collection_step: step size for the collection (default 300) - this should be the interval at which data is collected
    """

    metrics = metrics_client()

    step = int(step) if isinstance(step, str) else step

    query = f"""
    label_replace(
        sum by (ctl_asn_src) (
            avg_over_time(
                sflow_bytes{{ctl_org_id="{org_id}", ctl_port_id_dst="{port_id}", ctl_asn_dst="{asn}"}}
            )
        ) * 8 / {collection_step} or vector(0),
        "metric", "bps_in", "", ""
    )
    or
    label_replace(
        max by (ctl_asn_src) (
            max_over_time(
                sflow_bytes{{ctl_org_id="{org_id}", ctl_port_id_dst="{port_id}", ctl_asn_dst="{asn}"}}
            )
        ) * 8 / {collection_step} or vector(0),
        "metric", "bps_in_max", "", ""
    )
    or
    label_replace(
        sum by (ctl_asn_dst) (
            avg_over_time(
                sflow_bytes{{ctl_org_id="{org_id}", ctl_port_id_src="{port_id}", ctl_asn_src="{asn}"}}
            )
        ) * 8 / {collection_step} or vector(0),
        "metric", "bps_out", "", ""
    )
    or
    label_replace(
        max by (ctl_asn_dst) (
            max_over_time(
                sflow_bytes{{ctl_org_id="{org_id}", ctl_port_id_src="{port_id}", ctl_asn_src="{asn}"}}
            )
        ) * 8 / {collection_step}  or vector(0),
        "metric", "bps_out_max", "", ""
    )
    """

    return metrics.query_range(query, start=start, end=end, step=step)


def query_graph_asn_pair(
    org_id: int,
    port_id: int,
    asn_src: int,
    asn_dst: int,
    step: str | int,
    start: str,
    end: str,
    collection_step: int = 300,
    **kwargs,
) -> QueryResult:
    """
    Queries bits per second for a specific ASN to ASN (in and out)

    This is done by looking for a match in `ctl_asn_src` for outgoing
    traffic and `ctl_asn_dst` for incoming traffic.

    Creates 4 metrics (from perspective of src ASN):

    - bps_in (avg of all incoming traffic as bits per second)
    - bps_out (avg of all outgoing traffic as bits per second)
    - bps_in_max (max of all incoming traffic as bits per second)
    - bps_out_max (max of all outgoing traffic as bits per second)

    Arguments:

    - org_id: Organization ID (aaactl ID) - the organization that stores the data
    - port_id: Port ID - needs to be the port for the source ASN
    - asn_src: Source ASN
    - asn_dst: Destination ASN
    - step: tick size (e.g. 15m)
    - start: start time (unix timestamp or relative time like -1h)
    - end: end time (unix timestamp or relative time like -1h)
    - collection_step: step size for the collection (default 300) - this should be the interval at which data is collected
    """

    metrics = metrics_client()

    step = int(step) if isinstance(step, str) else step

    query = f"""
    label_replace(
        sum(
            avg_over_time(
                sflow_bytes{{ctl_org_id="{org_id}", ctl_port_id_dst="{port_id}", ctl_asn_dst="{asn_src}", ctl_asn_src="{asn_dst}"}}
            )
        ) * 8 / {collection_step} or vector(0),
        "metric", "bps_in", "", ""
    )
    or
    label_replace(
        max(
            sum(
                max_over_time(
                    sflow_bytes{{ctl_org_id="{org_id}", ctl_port_id_dst="{port_id}", ctl_asn_dst="{asn_src}", ctl_asn_src="{asn_dst}"}}
                )
            )
        ) * 8 / {collection_step}  or vector(0),
        "metric", "bps_in_max", "", ""
    )
    or
    label_replace(
        max(
            sum(
                avg_over_time(
                    sflow_bytes{{ctl_org_id="{org_id}", ctl_port_id_src="{port_id}", ctl_asn_src="{asn_src}", ctl_asn_dst="{asn_dst}"}}
                )
            )
        ) * 8 / {collection_step} or vector(0),
        "metric", "bps_out", "", ""
    )
    or
    label_replace(
        sum(
            max_over_time(
                sflow_bytes{{ctl_org_id="{org_id}", ctl_port_id_src="{port_id}", ctl_asn_src="{asn_src}", ctl_asn_dst="{asn_dst}"}}
            )
        ) * 8 / {collection_step}  or vector(0),
        "metric", "bps_out_max", "", ""
    )
    """

    return metrics.query_range(query, start=start, end=end, step=step)


def asn_table(result: QueryResult, asn_names: dict[int, str]) -> list[dict]:
    """
    Returns a list of ASNs with their traffic data in the following format:

    ```json
    [
        {
            "asn": 1234,
            "name": "AS1234",
            "bps_in_current": 1234,
            "bps_in_average": 1234,
            "bps_in_max": 1234,
            "bps_out_current": 1234,
            "bps_out_average": 1234,
            "bps_out_max": 1234
        },
        ...
    ]
    ```

    Arguments:

    - result: QueryResult object as returned from query_graph_asn
    - asn_names: Mapping of ASN to name

    Example of asn_names:

    ```py
    {
        1234: "AS1234",
        5678: "AS5678"
    }
    ```

    Will fallback to "AS{asn}" if no name is found
    """

    result_data = []
    asn_data = {}

    for item in result.data.result:
        metric = item.metric

        asn = metric.get("ctl_asn_src") or metric.get("ctl_asn_dst")

        if not asn:
            continue

        asn = int(asn)
        metric_type = metric["metric"]

        if asn not in asn_data:
            asn_data[asn] = {
                "asn": asn,
                "name": asn_names.get(asn) or f"AS{asn}",
                "bps_in_current": None,
                "bps_in_average": None,
                "bps_in_max": None,
                "bps_out_current": None,
                "bps_out_average": None,
                "bps_out_max": None,
            }

        if metric_type in ["bps_in", "bps_out"]:
            current_value = item.values[-1][1]  # Get the most recent value
            average_value = sum(v[1] for v in item.values) / len(item.values)

            if metric_type == "bps_in":
                asn_data[asn]["bps_in_current"] = round(current_value)
                asn_data[asn]["bps_in_average"] = round(average_value)
            else:
                asn_data[asn]["bps_out_current"] = round(current_value)
                asn_data[asn]["bps_out_average"] = round(average_value)

        elif metric_type in ["bps_in_max", "bps_out_max"]:
            max_value = max(v[1] for v in item.values)

            if metric_type == "bps_in_max":
                asn_data[asn]["bps_in_max"] = round(max_value)
            else:
                asn_data[asn]["bps_out_max"] = round(max_value)

    result_data = list(asn_data.values())

    return result_data
