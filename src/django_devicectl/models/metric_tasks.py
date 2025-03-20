from fullctl.django.models import Task
from fullctl.django.tasks import register
import django_devicectl.mrtg as mrtg


@register
class InsertMetric(Task):

    class TaskMeta:
        limit = 10
    
    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_insert_metric"

    @property
    def generate_limit_id(self):
        return self.org.id

    @property
    def metric_data(self) -> dict:
        return self.param["kwargs"].get("data")

    def run(self, *args, **kwargs):
        data = self.metric_data
        mrtg.write_switch_to_switch(
            org_id=self.org.id,
            org_slug=self.org.slug,
            data=data
        )