import subprocess

from fullctl.django.management.commands.base import CommandInterface
from fullctl.django.tasks.orm import discover_tasks, fetch_task


class Command(CommandInterface):

    help = "Process task queue"

    always_commit = True

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("--forever", help="poll forever", action="store_true")

    def run(self, *args, **kwargs):
        forever = kwargs.get("forever")

        discover_tasks()

        self.log_info("fetching tasks")
        while True:
            task = fetch_task()
            if task:
                cmd = [
                    "python",
                    "manage.py",
                    "fullctl_work_task",
                    task._meta.app_label,
                    task._meta.model_name,
                    f"{task.id}",
                ]
                subprocess.run(cmd, timeout=task.timeout)

            if not forever:
                break
            break
