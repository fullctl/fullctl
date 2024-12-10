from django.core.management import call_command
from fullctl.django.models import Task
from fullctl.django.tasks import register

import django_ixctl.models.ixctl as models


@register
class RsConfGenerate(Task):

    """
    Regenerate RS config


    arguments to pass to `create_task`:

        - routeserver_config_id (id of routeserver_config instance)
    """

    class TaskMeta:
        # limit of 1, but this will be per rs
        # see generate_limit_id below
        limit = 1

    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_routeserver_config_gen"

    @property
    def generate_limit_id(self):
        """
        We want the task limit to be per routeserver_config so we
        include the routeserver_config id in the limit_id for the task
        """
        return self.param["args"][0]

    def run(self, routeserver_config_id, *args, **kwargs):
        """
        Regenerate the routeserver_config
        """
        routeserver_config = models.RouteserverConfig.objects.get(
            id=routeserver_config_id
        )
        routeserver_config.generate()


@register
class DeleteRevisions(Task):

    """
    Delete Revisions Task
    kwargs:
        - model - The target model - defaults to django_ixctl.RouteserverConfig
        - keep - The number of records to keep - default to 3
    """

    class Meta:
        proxy = True

    class HandleRef:
        tag = "delete_revisions_task"

    def run(self, *args, **kwargs):
        """
        Run deleterevisions command from django-revisions
        """
        model = kwargs.get("model", "django_ixctl.RouteserverConfig")
        keep = kwargs.get("keep", 3)
        call_command("deleterevisions", model, f"--keep={keep}")
        return self.output
