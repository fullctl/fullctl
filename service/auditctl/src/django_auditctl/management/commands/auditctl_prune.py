import json
import os
from datetime import timedelta

from django.conf import settings
from django.core.management import call_command
from django.utils import timezone
from django_auditctl.models.auditctl import Event

from fullctl.django.management.commands.base import CommandInterface
from fullctl.django.management.commands.utils import (
    batched_raw_delete,
    pattern_to_regex,
    validate_regex,
)


class Command(CommandInterface):
    """
    Prune old audit log events and optionally their associated tasks.

    Deletes events older than --max-age days (default: EVENT_MAX_AGE setting).
    Use --include/--exclude to filter by object_id using regex patterns.
    Bare ``*`` in patterns is expanded to ``.*`` for glob-style convenience.

    When --tasks is passed, also prunes tasks (via fullctl_manage_tasks prune)
    using the same --include/--exclude pattern matched against the task's
    limit_id. All task statuses are pruned (pending, running, completed,
    failed, cancelled).

    Nothing is deleted without --commit (dry-run by default).

    Examples::

        # Dry-run: see what would be pruned for high-volume event types
        auditctl_prune --include ".*(traffic|config/liveness|bgp/stats).*" --max-age 30

        # Prune events AND tasks for those patterns, keeping last 30 days
        auditctl_prune --include ".*(traffic|config/liveness|bgp/stats).*" --tasks --max-age 30 --commit

        # Prune everything older than 90 days, back up first
        auditctl_prune --max-age 90 --backup --output-path /tmp/audit-backups --commit

        # Prune everything EXCEPT liveness checks
        auditctl_prune --exclude ".*/config/liveness/.*" --max-age 30 --commit
    """

    help = "Prune old audit log event entries"

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument(
            "-a",
            "--max-age",
            type=int,
            help="Maximum age of entries to retain in days. If not specified `EVENT_MAX_AGE` will be used.",
        )
        parser.add_argument(
            "-o",
            "--output-path",
            type=str,
            help="Path where the dumped JSON will be stored. If omitted, the current directory will be used.",
        )
        filter_group = parser.add_mutually_exclusive_group()
        filter_group.add_argument(
            "--include",
            type=str,
            help=(
                "Only prune events whose object_id matches this regex pattern. "
                "Bare * is treated as .* for glob-style convenience. "
                'Example: ".*(traffic|config/liveness|bgp/stats).*"'
            ),
        )
        filter_group.add_argument(
            "--exclude",
            type=str,
            help=(
                "Only prune events whose object_id does NOT match this regex pattern. "
                "Bare * is treated as .* for glob-style convenience."
            ),
        )
        parser.add_argument(
            "--tasks",
            action="store_true",
            default=False,
            help=(
                "Also prune tasks (all statuses) using fullctl_manage_tasks prune, "
                "passing the same --include/--exclude and --max-age filters. "
                "Tasks are matched by limit_id."
            ),
        )
        parser.add_argument(
            "--backup",
            action="store_true",
            default=False,
            help="Back up pruned events to a JSON file before deleting. Use with --output-path to control location.",
        )

    def run(self, *args, **kwargs):
        max_age = kwargs.get("max_age")
        if max_age is None:
            max_age = settings.EVENT_MAX_AGE

        max_age_fmt = f"{max_age} days"

        cutoff_date = timezone.now() - timedelta(days=max_age)

        self.log_info(f"Pruning entries older than {max_age_fmt} ({cutoff_date})")

        queryset = Event.objects.filter(created__lt=cutoff_date)

        include_pattern = kwargs.get("include")
        exclude_pattern = kwargs.get("exclude")

        if include_pattern:
            regex = pattern_to_regex(include_pattern)
            validate_regex(regex, "include")
            self.log_info(f"Including only object_id matching: {regex}")
            queryset = queryset.filter(object_id__regex=regex)
        elif exclude_pattern:
            regex = pattern_to_regex(exclude_pattern)
            validate_regex(regex, "exclude")
            self.log_info(f"Excluding object_id matching: {regex}")
            queryset = queryset.exclude(object_id__regex=regex)

        if not queryset.exists():
            self.log_info("No Events to prune")
        else:
            self._prune_events(queryset, cutoff_date, **kwargs)

        if kwargs.get("tasks"):
            self._prune_tasks(max_age, include_pattern, exclude_pattern)

    def _prune_events(self, queryset, cutoff_date, **kwargs):
        """Back up and delete matched events."""
        if kwargs.get("backup"):
            self._backup_events(queryset, cutoff_date, **kwargs)

        if self.commit:
            total_deleted = batched_raw_delete(
                queryset,
                settings.EVENT_PRUNE_BATCH_SIZE,
                self.log_info,
                label="events",
            )
            self.log_info(f"Pruned {total_deleted} events.")
        else:
            self.log_info(f"Would prune {queryset.count()} events.")

    def _backup_events(self, queryset, cutoff_date, **kwargs):
        """Back up events to a JSON file before deletion."""
        output_path = kwargs.get("output_path", "")
        if not output_path:
            output_path = os.getcwd()

        date = cutoff_date.strftime("%Y-%m-%d_%H:%M:%S")
        file_path = os.path.join(output_path, f"pruned_audit_log_{date}.json")

        if self.commit:
            self.log_info(f"Backing up entries to {output_path}")
            with open(file_path, "w") as f:
                f.write("[")
                first = True
                for entry in queryset.iterator(
                    chunk_size=settings.EVENT_PRUNE_BATCH_SIZE
                ):
                    if not first:
                        f.write(",\n")
                    json.dump(entry.to_dict(), f)
                    first = False
                f.write("]")
            self.log_info(f"Entries backed up to {file_path}")
        else:
            self.log_info(f"Would back up entries to {output_path}")

    def _prune_tasks(self, age, include_pattern, exclude_pattern):
        """Run fullctl_manage_tasks prune with the same filters."""
        self.log_info("Pruning tasks ...")

        cmd_kwargs = {
            "commit": self.commit,
            "age": age,
            "status": ["pending", "running", "completed", "failed", "cancelled"],
        }

        if include_pattern:
            cmd_kwargs["include"] = include_pattern
        elif exclude_pattern:
            cmd_kwargs["exclude"] = exclude_pattern

        call_command("fullctl_manage_tasks", "prune", **cmd_kwargs)
