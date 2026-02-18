from fullctl.django.models import Task
from fullctl.django.tasks import register
from fullctl.django.tasks.qualifiers import ConcurrencyLimit

import account.models

__all__ = ["UpdatePermissions"]


@register
class UpdatePermissions(Task):
    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_update_permissions"

    class TaskMeta:
        qualifiers = [
            ConcurrencyLimit(1),
        ]

    @property
    def generate_limit_id(self):
        if self.param["kwargs"].get("target_org"):
            return "org:" + str(self.param["kwargs"].get("target_org"))
        return ""

    def run(self, target_org=None, *args, **kwargs):
        if target_org:
            org = account.models.Organization.objects.get(id=target_org)
            account.models.ManagedPermission.apply_roles_org(org)
        else:
            account.models.ManagedPermission.apply_roles_all()
