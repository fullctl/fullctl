import os
import threading
import time
import traceback

import django.db
import psycopg
import structlog
from django.conf import settings
from django.utils import timezone

from fullctl.django.management.commands.base import CommandError, CommandInterface
from fullctl.django.models import Task, TaskHeartbeat
from fullctl.django.tasks.orm import (
    TaskAlreadyStarted,
    TaskClaimed,
    claim_task,
    fetch_task,
    set_task_as_failed,
    specify_task,
    work_task,
)

TASK_TRACK_INTERVAL_SECONDS = getattr(settings, "TASK_TRACK_INTERVAL_SECONDS", 10)

log = structlog.get_logger("django")


class Command(CommandInterface):
    help = "Process the specified task"

    always_commit = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.stop_event = threading.Event()

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

        parser.add_argument(
            "-t",
            "--max-tasks",
            help="Exit after processing this many tasks (to allow respawning). This is only used when self-selecting.",
            type=int,
            # 0 means unlimited
            default=1000,
        )

    def handle(self, *args, **kwargs):
        self.task_id = kwargs.get("task_id")
        self.poll_interval = float(kwargs.get("poll_interval")) or 3.0
        self.once = kwargs.get("once")
        self.max_tasks = int(kwargs.get("max_tasks") or 0)
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

    def finalize_task_processing(self, task: int | Task):
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

    def track_task_processing(self):
        """
        Track the task processing during the command run

        The function updates the TaskHeartbeart while the task is running

        This is done at intervals of the specified - env var `TASK_TRACK_INTERVAL_SECONDS`

        The `timestamp` field in the TaskHeartbeat model is used to check if the task is still running and not dead.
        """
        while not self.stop_event.is_set():
            try:
                TaskHeartbeat.objects.update_or_create(
                    task_id=self.task_id,
                    defaults={
                        "timestamp": timezone.now(),
                    },
                )
            except Exception as exc:
                log.exception("Error in heartbeat loop", exc=exc)
            time.sleep(TASK_TRACK_INTERVAL_SECONDS)

    def before_run(self):
        """
        This function starts a thread to track the task processing
        """
        super().before_run()
        self.thread = threading.Thread(target=self.track_task_processing)
        self.thread.start()

    def after_run(self):
        """
        This function stops the thread to track the task processing
        """
        super().after_run()
        self.stop_event.set()
        self.thread.join()

    def run(self, *args, **kwargs):
        """
        Execute the specified task
        """
        if not self.task_id:
            return

        task = specify_task(Task.objects.get(id=self.task_id))
        self.log_info(f"Processing {task}")

        try:
            work_task(task)
        except (TaskClaimed, TaskAlreadyStarted):
            log.debug("Task already claimed or started by another worker", task=task)
            return
        finally:
            self.finalize_task_processing(task)

    def poll_tasks(self):
        """
        Polls for tasks and processes them
        """
        self.log_info("Worker " + self.worker_id + " polling for tasks.")
        tasks_processed = 0

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
                    tasks_processed += 1

                    # Exit if we've reached the max tasks limit
                    if self.max_tasks > 0 and tasks_processed >= self.max_tasks:
                        self.log_info(
                            f"Worker {self.worker_id} reached task limit ({self.max_tasks}), exiting"
                        )
                        break

                    if self.once:
                        break
                else:
                    time.sleep(self.poll_interval)
            except (TaskClaimed, TaskAlreadyStarted):
                log.debug(
                    "Task already claimed or started by another worker", task=task
                )
            except Exception as exc:
                log.exception("Error polling tasks", exc=exc, typ=type(exc))
                try:
                    self.handle_outer_error(exc, task=task)
                except Exception as exc:
                    log.exception("Error in task run", exc=exc)
                    raise CommandError("Error in task run")

    def handle_outer_error(self, exc: Exception, retries: int = 5, task: Task = None):
        """
        Handles errors that happen when setting up the task for processing

        This catches issues such as temporary database failures.
        """

        try:
            if isinstance(
                exc, (psycopg.OperationalError, django.db.utils.OperationalError)
            ):
                # Close old connections to force reconnection on next DB operation
                django.db.close_old_connections()
                log.info("Closed old DB connections due to database error")

                # db issue, give time to recover
                if self.task_id:
                    time.sleep(3)
                else:
                    # just kill the worker, it'll respawn and reconnect
                    retries = 0
                    raise exc

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
            else:
                raise exc
