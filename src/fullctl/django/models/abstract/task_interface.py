import datetime
import json
import subprocess
import traceback
import time

import pytz
from django.utils.translation import gettext_lazy as _
from django.core.exceptions import ValidationError
from django.db import models
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

from fullctl.django.models.abstract.base import HandleRefModel
from fullctl.django.tasks.util import worker_id

# from fullctl.django.tasks import launch_task


class TaskClaimed(IOError):
    def __init__(self, task):
        super().__init__(f"Task already claimed by another worker: {task}")


class WorkerUnqualified(IOError):
    def __init__(self, task, qualifier):
        super().__init__(
            f"Worker does not qualify to process this task: {task}, {qualifier}"
        )


class TaskLimitError(IOError):
    pass


class TaskAlreadyStarted(IOError):
    pass


class Task(HandleRefModel):

    """
    Describes an asynchronous task

    Task status values:
        - pending: task waiting for execution
        - running: task is currently executing
        - completed: task completed succesfully
        - failed: task ended due to error
        - cancelled: task canceled
    """

    op = models.CharField(max_length=255)

    status = models.CharField(
        max_length=255,
        choices=(
            ("pending", _("Pending")),
            ("running", _("Running")),
            ("completed", _("Completed")),
            ("failed", _("Failed")),
            ("cancelled", _("Cancelled")),
        ),
        default="pending",
    )

    param_json = models.TextField(
        blank=True, null=True, help_text="json containing args and kwargs"
    )
    error = models.TextField(
        blank=True,
        null=True,
        help_text="if the task failed will contain traceback or error info",
    )
    output = models.TextField(
        blank=True,
        null=True,
        help_text="task output - can also be used to store results",
    )

    timeout = models.IntegerField(
        null=True, blank=True, default=None, help_text="task timeout in seconds"
    )

    time = models.FloatField(default=0.0, help_text="time sepnt in seconds")

    source = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        default=worker_id,
        help_text="host id where task was triggered",
    )

    queue_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="task queue id (celery task id or orm worker id)",
    )

    parent = models.ForeignKey(
        "django_fullctl.Task", on_delete=models.CASCADE, null=True, blank=True
    )

    # limit concurrent instances of this task type being processed
    limit = None

    class Meta:
        abstract = True

    class HandleRef:
        tag = "task"

    @classmethod
    def validate_limits(cls, op):
        if cls.limit is None:
            return

        count = cls.objects.filter(op=op, status__in=["pending", "running"]).count()
        if cls.limit >= count:
            raise TaskLimitError()

    @classmethod
    def create_task(cls, param_args=None, param_kwargs=None, **kwargs):

        op = cls.HandleRef.tag

        cls.validate_limits(op)

        param = {"args": param_args or [], "kwargs": param_kwargs or {}}

        task = cls(op=op, param=param, status="pending", **kwargs)
        task.clean()
        task.save()
        return task

    @property
    def param(self):
        """
        Will return a dict from the param_json value
        """
        if self.param_json:
            return json.loads(self.param_json)
        return {"args": [], "kwargs": {}}

    @param.setter
    def param(self, param):
        """
        Will take a dict and convert to json and
        store in the param_json field
        """
        self.param_json = json.dumps(param)

    @property
    def qualifies(self):

        qualifiers = getattr(self._meta.model, "qualifiers", [])

        for qualifier in qualifiers:
            if not qualifier.check(self):
                raise WorkerUnqualified(self, qualifier)

        return True

    def __str__(self):
        return f"{self.__class__.__name__}({self.id}): {self.param['args']}"

    def clean(self):
        super().clean()
        try:
            if self.param_json:
                json.loads(self.param_json)
        except Exception as exc:
            raise ValidationError(f"Parameters could not be JSON encoded: {exc}")

    def cancel(self, reason):
        self._cancel(reason)

    def _cancel(self, reason):
        self.output = reason
        self.status = "cancelled"
        self.save()

    def _complete(self, output):
        self.output = output
        self.status = "completed"
        self.save()

    def _fail(self, error):
        self.error = error
        self.status = "failed"
        self.save()

    def _run(self):

        if self.status != "pending":
            raise TaskAlreadyStarted()

        self.status = "running"
        self.save()
        t_start = time.time()
        try:
            param = self.param
            output = self.run(*param["args"], **param["kwargs"])
            t_end = time.time()
            self.time = t_end - t_start
            self._complete(output)
        except Exception:
            self._fail(traceback.format_exc())

    def run(self, *args, **kwargs):
        """ extend in proxy model """
        raise NotImplementedError()

    def run_command(self, command):
        # TODO this needs to capture output
        subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
