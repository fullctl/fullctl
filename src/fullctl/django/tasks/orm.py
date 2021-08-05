"""
ORM based task delegation
"""
from django.db import IntegrityError
from django.db.models import Q
from django.apps import apps
from django.conf import settings
from fullctl.django.tasks.util import worker_id
from fullctl.django.models.abstract.task_interface import (
    Task,
    WorkerUnqualified,
    TaskClaimed,
)
from fullctl.django.models.concrete.tasks import TaskClaim, Task
from fullctl.django.tasks import specify_task


def fetch_task(**filters):
    """
    Checks for the next available and qualifying
    tasks and returns it
    """

    tasks = fetch_tasks(limit=1, **filters)
    if tasks:
        return tasks[0]
    return None


def fetch_tasks(limit=1, **filters):

    tasks = []

    # filter tasks waiting for execution
    qset = Task.objects.filter(status="pending", queue_id__isnull=True)

    if filters:
        qset = qset.filter(**filters)

    # order by date of creation
    qset = qset.order_by("created")

    # no pending tasks for this task model
    if not qset.exists():
        return tasks

    for task in qset:
        if task.parent_id and task.parent.status != "completed":
            if task.parent.status in ["failed", "cancelled"]:
                task.cancel(f"parent status: {task.parent.status}")
            continue
        try:
            task.qualifies
            tasks.append(specify_task(task))
        except WorkerUnqualified:
            continue

        if len(tasks) == limit:
            return tasks


def claim_task(task):

    """
    Claims the specified task
    """

    try:
        claim = TaskClaim.objects.create(task=task, worker_id=worker_id())
        task.queue_id = claim.worker_id
        task.save()
        return claim
    except IntegrityError as exc:
        print(exc)
        raise TaskClaimed(task)


def work_task(task):

    """
    processes the specified task
    """

    task._run()
