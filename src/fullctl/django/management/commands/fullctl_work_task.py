from django.contrib.contenttypes.models import ContentType
from fullctl.django.management.commands.base import CommandInterface
from fullctl.django.tasks.orm import work_task


class Command(CommandInterface):

    help = "Process the specified task"

    always_commit = True

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("task_app_label", nargs="?")
        parser.add_argument("task_model", nargs="?")
        parser.add_argument("task_id", nargs="?")

    def run(self, *args, **kwargs):
        task_app_label = kwargs.get("task_app_label")
        task_model = kwargs.get("task_model")
        task_id = kwargs.get("task_id")

        try:
            TaskModel = ContentType.objects.get(
                app_label=task_app_label, model=task_model
            ).model_class()
        except ContentType.DoesNotExist:
            raise ValueError(f"Unknown task model: {task_app_label}.{task_model}")

        try:
            task = TaskModel.objects.get(id=task_id)
        except TaskModel.DoesNotExist:
            raise ValueError(f"{TaskModel} instance {task_id} not found")

        self.log_info(f"Processing {task}")
        work_task(task)
        self.log_info(f"Done!")
