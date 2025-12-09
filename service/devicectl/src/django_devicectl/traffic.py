import os
import time

import fullctl.graph.mrtg.rrd as mrtg_rrd
from django.conf import settings


def start_time_and_duration(start_time: int, duration: int):
    """
    Helper function to return start_time and duration
    """

    if not start_time:
        start_time = int(time.time())
    else:
        start_time = int(start_time)

    if not duration:
        duration = 86400
    else:
        duration = int(duration)

    return start_time, duration


def get_traffic_for_obj(obj: object, start_time: int, duration: int):
    """
    Loads traffic data for object (device, physical port, virtual port etc.)
    """

    start_time, duration = start_time_and_duration(start_time, duration)

    if not getattr(obj, "meta", None) or "graph" not in obj.meta:
        return []

    graph_file = os.path.join(settings.GRAPHS_PATH, obj.meta.get("graph"))

    if not os.path.exists(graph_file):
        return {}

    traffic_data = mrtg_rrd.load_rrd_file(graph_file, start_time, duration)
    traffic_data = sorted(traffic_data, key=lambda x: -x["timestamp"])

    # set id on each data point
    for data_point in traffic_data:
        data_point["id"] = obj.id

    return traffic_data


def get_traffic_for_group(group_type: str, id: str, start_time: int, duration: int):
    """
    Loads traffic data for group of objects (device, physical port, virtual port etc.)
    """

    start_time, duration = start_time_and_duration(start_time, duration)

    if group_type not in ["ixctl-ix"]:
        raise ValueError(f"Unknown group type {group_type}")

    try:
        int(id)
    except ValueError:
        raise ValueError(f"Invalid id {id}")

    graph_file = os.path.join(settings.GRAPHS_PATH, f"{group_type}-{id}.rrd")

    if not os.path.exists(graph_file):
        return []

    traffic_data = mrtg_rrd.load_rrd_file(graph_file, start_time, duration)
    traffic_data = sorted(traffic_data, key=lambda x: -x["timestamp"])

    # set id on each data point
    for data_point in traffic_data:
        data_point["id"] = id

    return traffic_data
