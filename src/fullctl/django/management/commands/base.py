import logging
import traceback
import socket

from django.conf import settings
from django.db import transaction
from django.core.management.base import BaseCommand

import reversion

from fullctl.django.auditlog import auditlog
from fullctl.django.tasks.orm import worker_id


class PretendMode(IOError):
    pass


class CommandInterface(BaseCommand):

    """
    Interface for fullctl commands

    - database transactions
    - auditlog enabled
    - reversion
    - task queueable
    """

    # if set to `False` command will by default run in
    # pretend mode and provide a `--commit` flag to
    # allow it to step into committal mode
    always_commit = False

    # enable auditlogging for command
    auditlog_enabled = True

    @property
    def log(self):
        if not hasattr(self, "_log"):
            self._log = logging.getLogger(__name__)
        return self._log

    def add_arguments(self, parser):
        if not self.always_commit:
            parser.add_argument("--commit", action="store_true", help="Commit changes")

    @auditlog()
    def handle(self, auditlog=None, *args, **kwargs):
        self.auditlog_context = auditlog
        self.output = []

        if not self.always_commit:
            self.commit = kwargs.get("commit")
        else:
            self.commit = True

        command_name = self.__class__.__module__.split(".")[-1]
        auditlog.append_data(
            command_args=args,
            command_kwargs=kwargs,
            command_name=command_name,
            clean=True,
        )
        auditlog.set("info", f"{worker_id()}:{command_name}")

        try:
            with reversion.create_revision():
                self.run(*args, **kwargs)
                if not self.commit:
                    raise PretendMode()
        except PretendMode:
            transaction.rollback()
            self.log_info(
                "Command was executed in pretend mode, all changes have been rolled back. To run command in committal mode set the --commit flag"
            )
        except Exception:
            transaction.rollback()
            err_txt = traceback.format_exc()
            auditlog.append_data(error=f"{err_txt}")
            self.log_error(err_txt)

        if self.auditlog_enabled and self.commit:
            auditlog.append_data(output="\n".join(self.output))
            auditlog.log(f"command")

    def log_debug(self, msg):
        self.log.debug(msg)
        self.stdout.write(msg)

    def log_info(self, msg):
        self.log.info(msg)
        self.output.append(msg)
        self.stdout.write(msg)

    def log_error(self, msg):
        self.log.error(msg)

    def run(self, *args, **kwargs):
        raise NotImplementedError()
