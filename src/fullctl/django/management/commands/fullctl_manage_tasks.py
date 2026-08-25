from datetime import timedelta

from django.conf import settings
from django.core.management.base import CommandParser
from django.utils import timezone

from fullctl.django.management.commands.base import CommandInterface
from fullctl.django.management.commands.utils import (
    batched_raw_delete,
    pattern_to_regex,
    validate_regex,
)
from fullctl.django.models import Task


class Command(CommandInterface):
    """
    Manage fullctl tasks.

    Subcommands:

    **prune** -- Delete old tasks by age, status, and limit_id pattern.

    Deletes tasks older than --age days (default: TASK_DEFAULT_PRUNE_AGE)
    with matching --status (default: TASK_DEFAULT_PRUNE_STATUS).
    Use --include/--exclude to filter by limit_id using regex patterns.
    Bare ``*`` in patterns is expanded to ``.*`` for glob-style convenience.

    Patterns in the TASK_DEFAULT_PRUNE_EXCLUDE setting are always excluded,
    even when --include is used.

    Nothing is deleted without --commit (dry-run by default).

    Task.parent cascades, so pruning a task also deletes its descendant tasks
    even where those do not match --age, --status or the patterns.

    .. note::

        Changed in 1.16: --exclude takes a single limit_id regex; it used to
        take a list of task op names. TASK_DEFAULT_PRUNE_EXCLUDE changed the
        same way. Deployments must rewrite both, and any prune cron
        invocations, before upgrading.

    Examples::

        # Dry-run: see how many tasks would be pruned
        fullctl_manage_tasks prune --age 30

        # Prune only traffic/liveness/stats tasks older than 30 days
        fullctl_manage_tasks prune --include ".*(traffic|config/liveness|bgp/stats).*" --age 30 --commit

        # Prune all statuses (including pending/running) for a pattern
        fullctl_manage_tasks prune --include ".*/config/liveness/.*" --status pending running completed failed cancelled --age 30 --commit

        # Prune everything except liveness tasks
        fullctl_manage_tasks prune --exclude ".*/config/liveness/.*" --age 30 --commit

    Settings::

        TASK_DEFAULT_PRUNE_AGE      -- Default max age in days (default: 30)
        TASK_DEFAULT_PRUNE_STATUS   -- Default statuses to prune (default: completed, failed, cancelled)
        TASK_DEFAULT_PRUNE_EXCLUDE  -- List of limit_id patterns always excluded from pruning
        TASK_PRUNE_BATCH_SIZE       -- Rows deleted per batch (default: 10000)
    """

    help = "Manage fullctl tasks"

    def add_arguments(self, parser: CommandParser):
        """Add arguments to the command."""
        super().add_arguments(parser)
        subparsers = parser.add_subparsers(dest="subcommand")
        prune_parser = subparsers.add_parser("prune")
        prune_parser.add_argument(
            "--age",
            default=settings.TASK_DEFAULT_PRUNE_AGE,
            help="Maximum age in days for tasks to retain (default: TASK_DEFAULT_PRUNE_AGE).",
            type=float,
        )
        prune_parser.add_argument(
            "--status",
            nargs="+",
            default=settings.TASK_DEFAULT_PRUNE_STATUS,
            help="List of task statuses to prune (default: TASK_DEFAULT_PRUNE_STATUS).",
        )

        filter_group = prune_parser.add_mutually_exclusive_group()
        filter_group.add_argument(
            "--include",
            type=str,
            help=(
                "Only prune tasks whose limit_id matches this regex pattern. "
                "Bare * is treated as .* for glob-style convenience. "
                'Example: ".*(traffic|config/liveness|bgp/stats).*"'
            ),
        )
        filter_group.add_argument(
            "--exclude",
            type=str,
            help=(
                "Only prune tasks whose limit_id does NOT match this regex pattern. "
                "Bare * is treated as .* for glob-style convenience."
            ),
        )

    def run(self, *args, **options):
        """Handle the command."""
        if options["subcommand"] == "prune":
            self.prune_tasks(**options)

    def prune_tasks(self, age: float, status: list[str], **kwargs):
        """Prune tasks older than a certain age."""
        age = float(age)
        cutoff = timezone.now() - timedelta(days=age)

        self.log_info(
            f"Pruning {', '.join(status)} tasks older than {age} days ({cutoff}) ..."
        )

        qset = Task.objects.filter(
            status__in=status,
            updated__lt=cutoff,
        )

        include_pattern = kwargs.get("include")
        exclude_pattern = kwargs.get("exclude")

        if include_pattern:
            regex = pattern_to_regex(include_pattern)
            validate_regex(regex, "include")
            self.log_info(f"Including only limit_id matching: {regex}")
            qset = qset.filter(limit_id__regex=regex)
        elif exclude_pattern:
            regex = pattern_to_regex(exclude_pattern)
            validate_regex(regex, "exclude")
            self.log_info(f"Excluding limit_id matching: {regex}")
            qset = qset.exclude(limit_id__regex=regex)

        # Always apply default exclusions from settings (list of limit_id patterns
        # that should never be pruned, independent of CLI --include/--exclude).
        default_excludes = getattr(settings, "TASK_DEFAULT_PRUNE_EXCLUDE", [])
        for pattern in default_excludes:
            regex = pattern_to_regex(pattern)
            validate_regex(regex, "TASK_DEFAULT_PRUNE_EXCLUDE")
            self.log_info(f"Default-excluding limit_id matching: {regex}")
            qset = qset.exclude(limit_id__regex=regex)

        count = qset.count()

        if count == 0:
            self.log_info("No tasks to prune")
            return

        if not self.commit:
            self.log_info(f"Would prune {count} tasks")
            return

        batch_size = getattr(settings, "TASK_PRUNE_BATCH_SIZE", 10000)
        total_deleted = batched_raw_delete(
            qset, batch_size, self.log_info, label="tasks"
        )

        self.log_info(f"Pruned {total_deleted} tasks")
