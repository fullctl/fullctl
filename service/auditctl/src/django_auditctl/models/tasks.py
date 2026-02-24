import django_auditctl.models.auditctl as models
from django_auditctl.event_handlers import get_handler_by_tag, get_handlers
from django_auditctl.heartbeat import process_overdue

from fullctl.django.models import Task
from fullctl.django.tasks import register


@register
class ExecuteEventHandler(Task):
    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_execute_event_handler"

    @classmethod
    def create_task(cls, event, handler_tag):
        task = super().create_task(str(event.id), handler_tag)
        models.EventTask.objects.create(event=event, task=task)

    @classmethod
    def create_tasks(cls, event):
        for handler in get_handlers(event):
            if handler.qualifies:
                cls.create_task(event, handler.HandleRef.tag)

    @property
    def handler_tag(self):
        return self.param["args"][1]

    @property
    def event(self):
        return models.Event.objects.get(id=self.param["args"][0])

    @property
    def generate_limit_id(self):
        """
        We are currently not limiting these types of tasks, but setting
        the limit id allows us to quickly identify the task type and the
        related event object id.
        """
        return f"{self.event.object_id}:{self.handler_tag}"

    def run(self, *args, **kwargs):
        handler = get_handler_by_tag(self.handler_tag)

        if not handler:
            raise KeyError(f"handler {self.handler_tag} not found")
        handler = handler(self.event)
        handler()


@register
class HearbeatCheck(Task):
    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_heartbeat_check"

    class TaskMeta:
        limit = 1

    def generate_limit_id(self):
        return "heartbeat_check"

    def run(self, *args, **kwargs):
        process_overdue()
