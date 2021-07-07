from io import StringIO

from django.utils.translation import gettext_lazy as _
from django.core.management import call_command

from fullctl.django.models.abstract.task_interface import Task


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
