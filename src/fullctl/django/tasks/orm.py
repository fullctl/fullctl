"""
ORM based task delegation
"""
import os
import socket
from django.db.models import Q
from django.apps import apps
from django.conf import settings
from fullctl.django.models.abstract.task_interface import Task, WorkerUnqualified

TASK_MODELS = []


def worker_id():

    """
    Returns the worker id for this instance

    This can be specified manually through the
    `TASK_ORM_WORKER_ID` setting

    If unspecified will default to hostname:pid
    """

    return getattr(
        settings, "TASK_ORM_WORKER_ID", f"{socket.gethostname()}:{os.getpid()}"
    )


def dicover_tasks():

    """
    Cycle through all django models and identify
    task models
    """

    if TASK_MODELS:
        return TASK_MODELS

    for model in apps.get_models():
        if isinstance(model, Task):
            TASK_MODELS.append(model)


def fetch_task():

    """
    Checks for the next available and qualifying
    tasks and returns it
    """

    for model in TASK_MODELS:

        # filter tasks waiting for execution
        qset = model.objects.filter(status="pending", queue_id__isnull=True)

        # filter tasks that aren't changed to parent task
        # or where the parent is finished
        qset = qset.filter(Q(parent__isnull=True) | Q(parent__status == "completed"))

        # order by date of creation
        qset = qset.order_by("created")

        # no pending tasks for this task model
        if not qset.exists():
            continue

        for task in qset:
            try:
                task.qualifies
                return task
            except WorkerUnqualified:
                continue


def work_task(task):

    """
    Claims and processes the specified task
    """

    wid = worker_id()
    task.refresh_from_db()
    task.claim(wid)
    task._run()
