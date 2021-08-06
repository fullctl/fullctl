"""
Contains a bunch of concrete models to help testing
"""

from fullctl.django.models import Task
from fullctl.django.tasks import register, qualifiers




@register
class TestTask(Task):

    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_test"

    def run(self, a, b, *args, **kwargs):
        return (a+b)

@register
class ParentTestTask:

    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_parent_test"

    def run(self, a, *args, **kwargs):
        b = int(self.parent.output)
        return (a+b)


@register
class QualifierTestTask(TestTask):

    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_qualifier_test"

    class TaskMeta:
        qualifiers = [
            qualifiers.Setting("TEST_QUALIFIER", True),
        ]
