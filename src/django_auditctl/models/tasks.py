from fullctl.django.models import Task
from fullctl.django.tasks import register

import django_auditctl.models.auditctl as models
from django_auditctl.event_handlers import get_handler_by_tag, get_handlers


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
            cls.create_task(event, handler.HandleRef.tag)

    @property
    def handler_tag(self):
        return self.param["args"][1]

    @property
    def event(self):
        return models.Event.objects.get(id=self.param["args"][0])

    def run(self, *args, **kwargs):
        handler = get_handler_by_tag(self.handler_tag)

        if not handler:
            raise KeyError(f"handler {self.handler_tag} not found")
        handler = handler(self.event)
        handler()
