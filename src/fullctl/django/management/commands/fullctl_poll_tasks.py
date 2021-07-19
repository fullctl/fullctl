import subprocess
import reversion
import asyncio
import threading
import time

from fullctl.django.management.commands.base import CommandInterface
from fullctl.django.tasks.orm import discover_tasks, fetch_task, claim_task, TaskClaimed


class Command(CommandInterface):

    help = "Process task queue"

    always_commit = True

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("--forever", help="poll forever", action="store_true")
        parser.add_argument("--workers", help="number of concurrent  workers", type=int)


    def _run(self, *args, **kwargs):
        discover_tasks()
        forever = kwargs.get("forever")
        self.workers = int(kwargs.get("workers") or 1)
        if forever:
            self._run_forever(*args, **kwargs)
        else:
            self._run_once(*args, **kwargs)

    async def poll_tasks(self):

        sleep_interval = 1
        max_workers = self.workers
        active_workers = self.active_workers = []
        while True:

            time.sleep(sleep_interval)

            print("active workers", len(active_workers))

            active_workers = [aw for aw in active_workers if not aw.done()]

            print("active workers (cleaned)", len(active_workers))

            if len(active_workers) >= max_workers:
                self.log_debug("all workers busy, skipping")
                continue

            while len(active_workers) < max_workers:

                coroutine = self._test_command()
                active_worker = asyncio.run_coroutine_threadsafe(coroutine)
                active_workers.append(active_worker)


                continue
                task = fetch_task()

                if not task:
                    break
                if not self.claim_task(task):
                    continue

                coroutine = self.delegate_task(task, loop=loop)
                active_worker = asyncio.run_coroutine_threadsafe(coroutine, loop)
                active_worker.add_done_callback(lambda f: print("DONE!!!!"))
                active_workers.append(active_worker)

    async def _test_command(self):
        print("_test_command")
        p = await asyncio.subprocess_create_shell("echo 'hello'")
        print("process spawned")
        await p.wait()
        print("process done")

    def _run_forever(self, *args, **kwargs):
        sleep_interval = 1

        asyncio.run(self.poll_tasks())




    def claim_task(self, task):
        try:
            with reversion.create_revision():
                self.log_info(f"Claiming task {task}")
                return claim_task(task)
        except TaskClaimed:
            if not task.queue_id:
                err = "Task has a claim, but no queue id - this should never happen"
                task.status = "failed"
                task.error = err
                task.save()
                self.log_error(err)
            self.log_debug("Task already claimed, skipping")


    async def delegate_task(self, task, loop):
        self.log_info(f"Delegating task {task}")
        cmd = [
            "python",
            "manage.py",
            "fullctl_work_task",
            task._meta.app_label,
            task._meta.model_name,
            f"{task.id}",
        ]
        work_task = await asyncio.create_subprocess_shell(
            " ".join(cmd),
#            stdout=asyncio.subprocess.DEVNULL,
#            stderr=asyncio.subprocess.DEVNULL,
        )
        #await work_task.wait()
        print("subprocess finished")
        #await asyncio.wait_for(work_task,task.timeout)

