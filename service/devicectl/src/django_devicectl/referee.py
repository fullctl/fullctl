"""
Referee util
"""

import json
from typing import Union

from django.utils import timezone


def get_report_kind(report: str) -> Union[str, None]:
    """
    Returns the kind of the report based on the contents of the report

    Args:
        report (str): The report to check (json string)
    """

    report = json.loads(report)

    if isinstance(report, list):
        return "sequential"

    # stacked: if report is a dict, but does not have a _state key

    elif isinstance(report, dict) and "_state" not in report:
        return "stacked"

    # snapshot: if report is a dict, and has a _state key

    elif isinstance(report, dict) and "_state" in report:
        return "snapshot"

    # unknown
    return None


def delete_old_reports(device, max_age: int):
    """
    Removes any referee reports for device that are older than max_age

    Arguments:

        device (Device): The device to cleanup reports for

        max_age (int): The maximum age of reports to keep (seconds)
    """

    date = timezone.now() - timezone.timedelta(seconds=max_age)

    print("Culling old reports", device, date)

    device.referee_reports.filter(created__lt=date).delete()
