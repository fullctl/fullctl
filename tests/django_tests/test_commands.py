from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core import management
from django.core.management.base import CommandError
from django.test import override_settings
from django.utils import timezone

import tests.django_tests.testapp.models as models
from fullctl.django.management.commands.utils import (
    pattern_to_regex,
    pg_batch_delete_sql,
    validate_regex,
)
from fullctl.django.models import Task
from fullctl.django.models.concrete.tasks import TaskSchedule
from fullctl.django.tasks.orm import specify_task


def test_fullctl_poll_tasks(db, dj_account_objects):
    with pytest.raises(SystemExit):
        management.call_command("fullctl_poll_tasks", "--help")


def test_unresolved_task(db, dj_account_objects):
    task = models.UnregisteredTestTask.create_task()
    # No error is raised here, but the task is not resolved
    task = specify_task(task)
    assert task is None


@patch("fullctl.django.tasks.log")
def test_task_op_that_doesnt_exist(mock_logging, db, dj_account_objects):
    org = dj_account_objects.org
    task_schedule = TaskSchedule.objects.create(
        org=org,
        task_config={
            "tasks": [
                {
                    "op": "unregistered_task_testt",
                    "param": {
                        "args": [],
                    },
                }
            ],
        },
        description="test",
        repeat=True,
        interval=3600,
        schedule=timezone.now(),
    )

    tasks = task_schedule.spawn_tasks()
    assert Task.objects.count() == 0
    assert tasks == []
    mock_logging.error.assert_called_once_with(
        "Task operation not found", task_op="unregistered_task_testt"
    )


def test_fullctl_promote_user(db, dj_account_objects_c):
    management.call_command("fullctl_promote_user", "user_test_c", "--commit")
    User = get_user_model()
    user = User.objects.get(username="user_test_c")

    assert user.is_superuser is True
    assert user.is_staff is True


def test_fullctl_work_task(db, dj_account_objects):
    task = models.TestTask.create_task(1, 2)
    management.call_command("fullctl_work_task", "1")
    task = specify_task(Task.objects.get(id=1))

    assert task.status == "completed"
    assert int(task.output) == 3


def test_fullctl_work_task_self_select(db, dj_account_objects):
    task = models.TestTask.create_task(1, 2)
    management.call_command("fullctl_work_task", "--once")
    task = specify_task(Task.objects.get(id=1))

    assert task.status == "completed"
    assert int(task.output) == 3


@patch("fullctl.django.management.commands.fullctl_work_task.Command.run")
def test_fullctl_work_task_error_handling_in_run(mock_run, db, dj_account_objects):
    # test error handling of errors in `run` call
    task = models.TestTask.create_task(1, 2)
    mock_run.side_effect = Exception("Test exception")

    management.call_command("fullctl_work_task", "1")
    task = specify_task(Task.objects.get(id=1))

    assert task.status == "failed"
    assert "Test exception" in task.error


@patch("fullctl.django.management.commands.fullctl_work_task.Command.poll_tasks")
def test_fullctl_work_task_error_handling_in_poll_tasks(
    mock_poll_tasks, db, dj_account_objects
):
    # test error handling of errors in `poll_tasks` call
    task = models.TestTask.create_task(1, 2)
    mock_poll_tasks.side_effect = Exception("Test exception")

    management.call_command("fullctl_work_task", "--once")
    task = specify_task(Task.objects.get(id=1))

    # poll task failed, so task should be pending still and
    # not have a queue_id
    assert task.status == "pending"
    assert task.queue_id is None


@patch("fullctl.django.management.commands.base.CommandInterface.handle")
def test_fullctl_work_task_error_handling_in_handle(
    mock_handle, db, dj_account_objects
):
    # test error handling of errors in `handle` call
    task = models.TestTask.create_task(1, 2)
    mock_handle.side_effect = Exception("Test exception")

    management.call_command("fullctl_work_task", "1")
    task = specify_task(Task.objects.get(id=1))

    assert task.status == "failed"
    assert "Test exception" in task.error


def test_fullctl_work_task_fail(db, dj_account_objects):
    task = models.FailingTask.create_task()
    management.call_command("fullctl_work_task", "1")
    task = specify_task(Task.objects.get(id=1))

    assert task.status == "failed"


def test_fullctl_prune_completed_tasks(db, dj_account_objects):
    task = models.TestTask.create_task(1, 2)
    task.status = "completed"
    task.save()

    management.call_command("fullctl_manage_tasks", "prune", commit=True, age=0)

    assert Task.objects.count() == 0
    assert Task.objects.filter(id=task.id).count() == 0


def test_fullctl_prune_failed_tasks(db, dj_account_objects):
    task = models.TestTask.create_task(1, 2)
    task.status = "failed"
    task.save()

    management.call_command("fullctl_manage_tasks", "prune", commit=True, age=0)

    assert Task.objects.count() == 0
    assert Task.objects.filter(id=task.id).count() == 0


def test_fullctl_prune_cancelled_tasks(db, dj_account_objects):
    task = models.TestTask.create_task(1, 2)
    task.status = "cancelled"
    task.save()

    management.call_command("fullctl_manage_tasks", "prune", commit=True, age=0)

    assert Task.objects.count() == 0
    assert Task.objects.filter(id=task.id).count() == 0


def test_fullctl_doesnt_prune_pending_tasks(db, dj_account_objects):
    task = models.TestTask.create_task(1, 2)

    management.call_command("fullctl_manage_tasks", "prune", commit=True, age=0)

    assert Task.objects.count() == 1
    assert Task.objects.filter(id=task.id).count() == 1


def test_fullctl_doesnt_prune_running_tasks(db, dj_account_objects):
    task = models.TestTask.create_task(1, 2)
    task.status = "running"
    task.save()

    management.call_command("fullctl_manage_tasks", "prune", commit=True, age=0)

    assert Task.objects.count() == 1
    assert Task.objects.filter(id=task.id).count() == 1


def test_fullctl_doesnt_prune_young_tasks(db, dj_account_objects):
    task = models.TestTask.create_task(1, 2)
    task.status = "completed"
    task.save()

    management.call_command("fullctl_manage_tasks", "prune", commit=True, age=5)

    assert Task.objects.count() == 1
    assert Task.objects.filter(id=task.id).count() == 1


def test_fullctl_prune_pretend_mode(db, dj_account_objects):
    """Without --commit, tasks are not actually deleted."""
    task = models.TestTask.create_task(1, 2)
    task.status = "completed"
    task.save()

    management.call_command("fullctl_manage_tasks", "prune", age=0)

    assert Task.objects.count() == 1


# --- include / exclude tests ---


def _make_completed_task(model_cls, *args, limit_id="", **kwargs):
    """Create a task, mark it completed, and optionally set limit_id."""
    task = model_cls.create_task(*args, **kwargs)
    task.status = "completed"
    if limit_id:
        task.limit_id = limit_id
    task.save()
    return task


def test_fullctl_prune_include_pattern(db, dj_account_objects):
    """Only tasks whose limit_id matches --include are deleted."""
    _make_completed_task(models.TestTask, 1, 2, limit_id="v0.1/org-1/config/liveness/")
    _make_completed_task(models.FailingTask, limit_id="v0.1/org-1/bgp/session/")

    management.call_command(
        "fullctl_manage_tasks",
        "prune",
        commit=True,
        age=0,
        include=".*/config/liveness/.*",
    )

    remaining = list(Task.objects.values_list("limit_id", flat=True))
    assert remaining == ["v0.1/org-1/bgp/session/"]


def test_fullctl_prune_include_wildcard(db, dj_account_objects):
    """Bare * in --include is expanded to .* (glob-style wildcard)."""
    _make_completed_task(models.TestTask, 1, 2, limit_id="v0.1/org-1/config/liveness/")
    _make_completed_task(models.FailingTask, limit_id="v0.1/org-1/bgp/session/")

    management.call_command(
        "fullctl_manage_tasks",
        "prune",
        commit=True,
        age=0,
        include="*/config/liveness/*",
    )

    remaining = list(Task.objects.values_list("limit_id", flat=True))
    assert remaining == ["v0.1/org-1/bgp/session/"]


def test_fullctl_prune_exclude_pattern(db, dj_account_objects):
    """Tasks whose limit_id matches --exclude are kept; others are deleted."""
    _make_completed_task(models.TestTask, 1, 2, limit_id="v0.1/org-1/config/liveness/")
    _make_completed_task(models.FailingTask, limit_id="v0.1/org-1/bgp/session/")

    management.call_command(
        "fullctl_manage_tasks",
        "prune",
        commit=True,
        age=0,
        exclude=".*/config/liveness/.*",
    )

    remaining = list(Task.objects.values_list("limit_id", flat=True))
    assert remaining == ["v0.1/org-1/config/liveness/"]


def test_fullctl_prune_include_no_match(db, dj_account_objects):
    """--include pattern that matches nothing leaves all tasks intact."""
    _make_completed_task(models.TestTask, 1, 2, limit_id="v0.1/org-1/config/liveness/")

    management.call_command(
        "fullctl_manage_tasks", "prune", commit=True, age=0, include="no_match"
    )

    assert Task.objects.count() == 1


@override_settings(TASK_DEFAULT_PRUNE_EXCLUDE=[".*/config/liveness/.*"])
def test_fullctl_prune_default_exclude(db, dj_account_objects):
    """TASK_DEFAULT_PRUNE_EXCLUDE setting protects matching limit_ids from pruning."""
    _make_completed_task(models.TestTask, 1, 2, limit_id="v0.1/org-1/config/liveness/")
    _make_completed_task(models.FailingTask, limit_id="v0.1/org-1/bgp/session/")

    management.call_command("fullctl_manage_tasks", "prune", commit=True, age=0)

    remaining = list(Task.objects.values_list("limit_id", flat=True))
    assert remaining == ["v0.1/org-1/config/liveness/"]


@override_settings(TASK_DEFAULT_PRUNE_EXCLUDE=[".*/bgp/session/.*"])
def test_fullctl_prune_default_exclude_with_include(db, dj_account_objects):
    """TASK_DEFAULT_PRUNE_EXCLUDE is applied even when --include is used."""
    _make_completed_task(models.TestTask, 1, 2, limit_id="v0.1/org-1/config/liveness/")
    _make_completed_task(models.FailingTask, limit_id="v0.1/org-1/bgp/session/")

    # --include matches both, but default exclude protects bgp/session
    management.call_command(
        "fullctl_manage_tasks", "prune", commit=True, age=0, include="v0.1/.*"
    )

    remaining = list(Task.objects.values_list("limit_id", flat=True))
    assert remaining == ["v0.1/org-1/bgp/session/"]


# --- pattern_to_regex unit tests ---


def test_pattern_to_regex_bare_star():
    assert pattern_to_regex("foo/*/bar") == "foo/.*/bar"


def test_pattern_to_regex_already_dotstar():
    assert pattern_to_regex("foo/.*/bar") == "foo/.*/bar"


def test_pattern_to_regex_plain_regex():
    assert pattern_to_regex("task_.+_test") == "task_.+_test"


def test_pattern_to_regex_multiple_stars():
    assert pattern_to_regex("a/*/b/*/c") == "a/.*/b/.*/c"


def test_pattern_to_regex_double_star():
    assert pattern_to_regex("a/**/b") == "a/.*/b"


# --- validate_regex unit tests ---


def test_pattern_to_regex_leading_star():
    assert pattern_to_regex("*/config/liveness") == ".*/config/liveness"


@pytest.mark.parametrize(
    "pattern",
    [
        r"task_\d*",
        "task_[a-z]*",
        "task_(foo)*",
        "a/(x*|y)/b",
    ],
)
def test_pattern_to_regex_preserves_quantifiers(pattern):
    """A `*` that is a regex quantifier must not be widened to `.*`."""
    assert pattern_to_regex(pattern) == pattern


def test_pattern_to_regex_star_after_alternation():
    assert pattern_to_regex("(a|*)") == "(a|.*)"


def test_validate_regex_valid():
    validate_regex("task_.*", "test")


def test_validate_regex_invalid():
    with pytest.raises(CommandError, match="Invalid regex"):
        validate_regex("[invalid", "test")


# --- pg_batch_delete_sql unit tests ---
#
# The PostgreSQL branch of batched_raw_delete cannot run against the sqlite
# test database, so the generated statement is asserted directly.

INNER_SQL = 'SELECT "id" FROM "fullctl_task" WHERE "status" = %s LIMIT 10'


def test_pg_batch_delete_sql_no_children():
    sql = pg_batch_delete_sql("fullctl_task", INNER_SQL, [])
    assert sql.startswith("WITH batch AS MATERIALIZED (")
    assert "RECURSIVE" not in sql
    assert sql.endswith(
        'DELETE FROM "fullctl_task" USING batch WHERE "fullctl_task"."id" = batch."id"'
    )


def test_pg_batch_delete_sql_flat_children():
    sql = pg_batch_delete_sql(
        "fullctl_task",
        INNER_SQL,
        [("fullctl_task_heartbeat", "task_id"), ("fullctl_task_claim", "task_id")],
    )
    assert "RECURSIVE" not in sql
    assert (
        'cascade_0 AS (DELETE FROM "fullctl_task_heartbeat" '
        'WHERE "task_id" IN (SELECT "id" FROM batch))' in sql
    )
    assert (
        'cascade_1 AS (DELETE FROM "fullctl_task_claim" '
        'WHERE "task_id" IN (SELECT "id" FROM batch))' in sql
    )


def test_pg_batch_delete_sql_self_fk_expands_to_closure():
    """
    A self-FK must drive a recursive closure, not a flat cascade -- otherwise
    cascade-deleted child tasks keep their heartbeat/claim rows and the
    statement aborts on an FK violation.
    """
    sql = pg_batch_delete_sql(
        "fullctl_task",
        INNER_SQL,
        [
            ("fullctl_task_heartbeat", "task_id"),
            ("fullctl_task_claim", "task_id"),
            ("fullctl_task", "parent_id"),
        ],
    )

    assert sql.startswith("WITH RECURSIVE batch AS MATERIALIZED (")
    assert (
        'closure AS (SELECT "id" FROM batch UNION '
        'SELECT child."id" FROM "fullctl_task" child '
        'JOIN closure ON (child."parent_id" = closure."id"))' in sql
    )

    # the self-FK is never emitted as a flat cascade ...
    assert 'DELETE FROM "fullctl_task" WHERE "parent_id"' not in sql
    # ... and every other child table is cleaned for the whole closure
    for table in ("fullctl_task_heartbeat", "fullctl_task_claim"):
        assert (
            f'DELETE FROM "{table}" WHERE "task_id" IN (SELECT "id" FROM closure)'
            in sql
        )

    assert sql.endswith(
        'DELETE FROM "fullctl_task" USING closure '
        'WHERE "fullctl_task"."id" = closure."id"'
    )


def test_pg_batch_delete_sql_multiple_self_fks():
    """Multiple self-FKs join with OR: a recursive CTE may self-reference once."""
    sql = pg_batch_delete_sql(
        "thing",
        'SELECT "id" FROM "thing"',
        [("thing", "parent_id"), ("thing", "replaces_id")],
    )
    assert (
        'JOIN closure ON (child."parent_id" = closure."id" '
        'OR child."replaces_id" = closure."id")' in sql
    )
    assert sql.count("SELECT child.") == 1
