from io import StringIO

from django.utils.translation import gettext_lazy as _
from django.core.management import call_command
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

from fullctl.django.models.abstract.base import HandleRefModel
import fullctl.django.models.abstract.task_interface as task_interface
import fullctl.django.tasks as tasks


class Task(task_interface.Task):
    class Meta:
        db_table = "fullctl_task"
        verbose_name = _("Task")
        verbose_name_plural = _("Tasks")


class TaskClaim(HandleRefModel):

    """
    Used by a worker to claim a task

    Whenever a worker claims a task the worker first
    needs to create a taskclaim object for it.

    This object has a unique constraint on the task,
    preventing race conditions when several workers
    are polling and claiming tasks asynchronously.
    """

    task = models.OneToOneField(Task, on_delete=models.CASCADE)
    worker_id = models.CharField(max_length=255)

    class Meta:
        db_table = "fullctl_task_claim"
        verbose_name = _("Claimed Task")
        verbose_name_plural = _("Claimed Tasks")

    class HandleRef:
        tag = "task_claim"


@tasks.register
class CallCommand(Task):

    """
    Django management tasks
    """

    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_callcommand"

    def run(self, *args, **kwargs):
        """
        Executes a django management command
        """

        out = StringIO()
        call_command(commit=True, *args, **kwargs, stdout=out)
        return f"{out.getvalue()}"
