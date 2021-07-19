from io import StringIO

from django.utils.translation import gettext_lazy as _
from django.core.management import call_command

from fullctl.django.models.abstract.base import HandleRefModel
from fullctl.django.models.abstract.task_interface import Task
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey


class TaskClaim(HandleRefModel):

    """
    Used by a worker to claim a task

    Whenever a worker claims a task the worker first
    needs to create a taskclaim object for it.

    This object has a unique constraint on the task,
    preventing race conditions when several workers
    are polling and claiming tasks asynchronously.
    """

    task_id = models.PositiveIntegerField()
    task_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    task = GenericForeignKey("task_type", "task_id")

    worker_id = models.CharField(max_length=255)

    class Meta:
        db_table = "fullctl_task_claim"
        verbose_name = _("Claimed Task")
        verbose_name_plural = _("Claimed Tasks")
        unique_together = (("task_type", "task_id"),)

    class HandleRef:
        tag = "task_claim"


class ManagementTask(Task):

    """
    Django management tasks
    """

    class Meta:
        db_table = "fullctl_task_command"
        verbose_name = _("Django Management Task")
        verbose_name_plural = _("Django Management Tasks")

    def op_call_command(self, *args, **kwargs):
        """
        Executes a django management command
        """

        out = StringIO()
        call_command(commit=True, *args, **kwargs, stdout=out)
        return f"{out.getvalue()}"
