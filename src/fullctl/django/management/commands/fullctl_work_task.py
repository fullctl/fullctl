import time
import os
import traceback

import psycopg
import structlog

from fullctl.django.management.commands.base import CommandInterface
from fullctl.django.models import Task
from fullctl.django.tasks.orm import (
    set_task_as_failed, 
    specify_task,
    work_task, 
    fetch_task,
    claim_task,
    TaskClaimed,
)

log = structlog.get_logger("django")


class Command(CommandInterface):
    help = "Process the specified task"

    always_commit = True

    @property
    def worker_id(self) -> str:
        # process id
        return str(os.getpid())

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("task_id", nargs="?")

        # interval argument
        parser.add_argument(
            "-i",
            "--poll-interval",
            help="delay between polling for tasks (seconds) when self selecting.",
            type=float,
            default=3.0,
        )

        # option to only self-select once
        parser.add_argument(
            "--once",
            help="Only self-select once, do not poll for additional tasks.",
            action="store_true",
        )

    def handle(self, *args, **kwargs):
        self.task_id = kwargs.get("task_id")
        self.poll_interval = float(kwargs.get("poll_interval")) or 3.0
        self.once = kwargs.get("once")
        try:
            # this will run the normal command handler
            # and also execute the task if the task_id is
            # specified in the arguments.
            #
            # it sets up some instance properties, so poll_tasks
            # is decoupled from the main handler
            super().handle(*args, **kwargs)

            # if task_id was not specified, it means the worker 
            # is "self-selecting" and will poll for tasks
            # based on the poll_interval
            if not self.task_id:
                self.poll_tasks()
            else:
                self.finalize_task_processing(int(self.task_id))
        except Exception as exc:
            log.exception("Error in task run", exc=exc)
            self.handle_outer_error(exc)

    def finalize_task_processing(self, task:int | Task):
        """
        Handles the finalization of the task processing
        Setting the task as failed if an error occurred

        Will also transport the error to the task if it the
        error occurred outside of the task execution logic
        """
        
        if isinstance(task, int):
            task = Task.objects.get(id=task)

        if getattr(self, "error", None) and not task.error:
            # failure, but wasn't within the context
            # of the task execution logic, transfer error
            # to task
            set_task_as_failed(task, self.error)

        if task.error:
            self.log_info("Task failed")
            self.log_error(task.error)
        else:
            self.log_info("Task finished")

        task.save()


    def run(self, *args, **kwargs):
        """
        Execute the specified task
        """
        if not self.task_id:
            return
        
        task = specify_task(Task.objects.get(id=self.task_id))
        self.log_info(f"Processing {task}")
        work_task(task)
        self.finalize_task_processing(task)


    def poll_tasks(self):
        """
        Polls for tasks and processes them
        """
        self.log_info("Worker " + self.worker_id + " polling for tasks.")
        while True:
            self.error = None
            task = None
            try:
                task = fetch_task()
                if task and not task.queue_id:
                    claim_task(task)
                    task = specify_task(task)
                    self.log_info(f"Processing {task}")
                    work_task(task)
                    self.finalize_task_processing(task)
                    if self.once:
                        break
                else:
                    time.sleep(self.poll_interval)
            except TaskClaimed:
                log.info("Task already claimed", task=task)
            except Exception as exc:
                log.exception("Error polling tasks", exc=exc)
                self.handle_outer_error(exc, task=task)

    def handle_outer_error(self, exc: Exception, retries: int = 5, task: Task = None):

        """
        Handles errors that happen when setting up the task for processing

        This catches issues such as temporary database failures.
        """

        try:
            if isinstance(exc, psycopg.OperationalError):
                # db issue, give time to recover
                time.sleep(3)
            
            if task:
                # set task as failed
                set_task_as_failed(task, traceback.format_exc())
            elif self.task_id:
                task = specify_task(Task.objects.get(id=self.task_id))
                # set task as failed
                set_task_as_failed(task, traceback.format_exc())
            
        except Exception as exc:
            log.exception(
                f"Error in task run (error cleanup, retries={retries})", exc=exc
            )
            if retries > 0:
                self.handle_outer_error(exc, retries - 1)
                # if error is never recovered during retries
                # task will end up orphaned as `pending` and will be eventually
                # re-queued by the poller whenever the max age limit is hit.
