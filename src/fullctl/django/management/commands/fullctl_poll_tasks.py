import asyncio
import uuid

import psycopg
import reversion
import structlog
from asgiref.sync import sync_to_async

from fullctl.django.management.commands.base import CommandInterface
from fullctl.django.tasks.orm import (
    TaskClaimed,
    claim_task,
    fetch_task,
    progress_schedules,
    tasks_max_time_reached,
)

log = structlog.get_logger("django")


class Worker:

    """
    Async task processor.

    Will run fullctl_work_task command async through asyncio.subprocess
    """

    def __init__(self):
        self.id = f"{uuid.uuid4()}"[:8]
        self.task = None
        self.process = None

    def set_task(self, task):
        if task and self.task:
            raise OSError("Worker has already been assiged a task")
        self.task = task
        self.process = None

    async def work(self):
        """
        Starts the worker on the tasks or waits for the currently
        assigned task to complete.

        Task is assigned through set_task
        """

        if not self.task:
            return
        self.task
        if not self.process:
            # no process has been spawned yet, run the command
            await self._run_command()
        else:
            # process has been spawned, check if it is done
            if self.process.returncode is not None:
                # its done, set task to None, indicating
                # that the worker is ready for more work
                self.set_task(None)

    async def _run_command(self):
        task = self.task
        cmd = [
            "python",
            "manage.py",
            "fullctl_work_task",
            f"{task.id}",
        ]
        p = await asyncio.create_subprocess_shell(
            " ".join(cmd),
        )
        self.process = p
        # print("Worker", self.id, p.pid, "subprocess spawned")


class Command(CommandInterface):
    help = "Process task queue"

    always_commit = True

    @property
    def worker_available(self):
        for worker in self.workers:
            if not worker.task:
                return True
        return False

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("--workers", help="number of concurrent  workers", type=int)
        parser.add_argument(
            "-i",
            "--poll-interval",
            help="delay between polling for tasks (seconds)",
            type=int,
            default=3,
        )

    def _run(self, *args, **kwargs):
        self.sleep_interval = 0.5
        self.poll_interval = float(kwargs.get("poll_interval")) or 3
        self.all_workers_busy = False
        self.workers_num = int(kwargs.get("workers") or 1)

        self.log_info(
            f"Starting task queue poller, {self.workers_num} workers, poll interval {self.poll_interval} seconds, sleep interval {self.sleep_interval} seconds"
        )

        self.workers = [Worker() for i in range(0, self.workers_num)]

        async def _main():
            await asyncio.gather(
                asyncio.create_task(self._poll_tasks()),
                asyncio.create_task(self._process_workers()),
                asyncio.create_task(self._progress_schedules()),
            )

        asyncio.run(_main())

    async def _process_workers(self):
        while True:
            try:
                await asyncio.sleep(self.sleep_interval)

                for worker in self.workers:
                    await worker.work()
            except Exception as exc:
                log.exception("Error processing workers", exc=exc)

    async def _poll_tasks(self):
        while True:
            task = None
            try:
                await asyncio.sleep(self.poll_interval)

                if not self.worker_available:
                    if not self.all_workers_busy:
                        self.log_info("All workers busy")
                        self.all_workers_busy = True
                    continue
                else:
                    if self.all_workers_busy:
                        self.log_info("Worker available")
                    self.all_workers_busy = False

                # check on stuck tasks and perform requeuing on those that have max times reached
                await sync_to_async(tasks_max_time_reached)()

                # django call needs to be wrapped in sync_to_async

                task = await sync_to_async(fetch_task)()

                if not task or task.queue_id:
                    continue

                self.log_info(f"New task {task}")

                # django call needs to be wrapped in sync_to_async

                await sync_to_async(self.claim_task)(task)

                await self.delegate_task(task)
            except psycopg.OperationalError as exc:
                log.exception("Error polling tasks (db error)", exc=exc)
                await asyncio.sleep(3)
            except Exception as exc:
                log.exception("Error polling tasks", exc=exc)

    async def _progress_schedules(self):
        while True:
            try:
                await asyncio.sleep(self.poll_interval)
                await sync_to_async(progress_schedules)()
            except Exception as exc:
                log.exception("Error progressing schedules", exc=exc)

    def claim_task(self, task):
        try:
            with reversion.create_revision():
                self.log_info(f"Claiming task {task}")
                return claim_task(task)
        except TaskClaimed:
            if not task.queue_id:
                err = "Task has a claim, but no queue id - likely in the middle of being claimed by other worker"
                self.log_debug(err)
            self.log_debug("Task already claimed, skipping")

    async def delegate_task(self, task):
        self.log_info(f"Delegating task {task}")
        while True:
            await asyncio.sleep(0.5)
            for worker in self.workers:
                if not worker.task:
                    worker.set_task(task)
                    return
