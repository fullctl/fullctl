"""
ORM based task delegation
"""
from django.db.models import Q
from django.apps import apps
from django.conf import settings
from fullctl.django.tasks.util import worker_id
from fullctl.django.models.abstract.task_interface import Task, WorkerUnqualified

TASK_MODELS = []


def discover_tasks():

    """
    Cycle through all django models and identify
    task models
    """

    if TASK_MODELS:
        return TASK_MODELS

    for model in apps.get_models():
        if issubclass(model, Task):
            TASK_MODELS.append(model)


def fetch_task():

    """
    Checks for the next available and qualifying
    tasks and returns it
    """

    for model in TASK_MODELS:

        # filter tasks waiting for execution
        qset = model.objects.filter(status="pending", queue_id__isnull=True)

        # order by date of creation
        qset = qset.order_by("created")

        # no pending tasks for this task model
        if not qset.exists():
            continue

        for task in qset:
            if task.parent_id and task.parent.status != "completed":
                continue
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
