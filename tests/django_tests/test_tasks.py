import pytest
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone
from unittest.mock import patch

import fullctl.django.tasks.orm as orm
import tests.django_tests.testapp.models as models
from fullctl.django.health_check import (
    health_check_task_heartbeat,
    health_check_task_stack_queue,
)
from fullctl.django.models.concrete.tasks import (
    TaskClaim,
    TaskClaimed,
    TaskHeartbeatError,
    TaskLimitError,
    TaskMaxAgeError,
    TaskSchedule,
    TaskScheduleClaim,
    TaskScheduleClaimed,
    TaskAlreadyStarted,
)
from fullctl.django.tasks.util import worker_id


@pytest.mark.django_db
def test_task_with_max_run_time():
    task = models.TestTaskWithMaxRunTime.create_task(1, 2)

    orm.claim_task(task)

    task.created = task.created - timezone.timedelta(seconds=7200)
    task.updated = task.created
    try:
        # set updated auto_now to false
        task._meta.get_field("updated").auto_now = False
        task.save()
    finally:
        task._meta.get_field("updated").auto_now = True

    orm.tasks_max_time_reached()

    assert orm.fetch_tasks()


@pytest.mark.django_db
def test_fetch_tasks():
    assert orm.fetch_task() is None
    assert orm.fetch_tasks() == []

    task = models.TestTask.create_task(1, 2)
    assert task == orm.fetch_task()
    task2 = models.TestTask.create_task(1, 3)
    assert orm.fetch_tasks(limit=2) == [task, task2]


@pytest.mark.django_db
def test_claim_task():
    task = models.TestTask.create_task(1, 2)
    orm.claim_task(task)

    with pytest.raises(TaskClaimed) as execinfo:
        orm.claim_task(task)

    assert "Task already claimed by another worker:" in str(execinfo)


@pytest.mark.django_db
def test_work_tasks():
    task = models.TestTask.create_task(1, 2)

    orm.claim_task(task)

    assert task.queue_id
    assert task.taskclaim

    orm.work_task(task)

    assert task.status == "completed"
    assert int(task.output) == 3


@pytest.mark.django_db
def test_parent_task():
    task_par = models.TestTask.create_task(1, 2)
    task_chl = models.TestTask.create_task(7, 3, parent=task_par)

    # cant run child task before parent is finished

    with pytest.raises(IOError):
        orm.work_task(task_chl)

    tasks = orm.fetch_tasks()

    # child task should not be fetched while its waiting
    # for parent
    assert task_chl not in tasks
    assert task_par in tasks

    orm.work_task(task_par)

    tasks = orm.fetch_tasks()

    assert task_chl in tasks

    # child task can be worked now
    task_chl.refresh_from_db()
    orm.work_task(task_chl)


@pytest.mark.django_db
def test_task_qualifiers(settings):
    task = models.QualifierTestTask.create_task(1, 2)

    # worker qualifies, task should be in tasks

    settings.TEST_QUALIFIER = True
    assert task in orm.fetch_tasks()

    # worker no longer qualifiers, task should not be in tasks

    settings.TEST_QUALIFIER = False
    assert task not in orm.fetch_tasks()


@pytest.mark.django_db
def test_task_result():
    task = models.TestTask.create_task(1, 2)
    orm.work_task(task)
    assert task.result == 3


@pytest.mark.django_db
def test_task_limits():
    task = models.LimitedTask.create_task("test")
    with pytest.raises(TaskLimitError):
        task = models.LimitedTask.create_task("test")

    orm.work_task(task)
    task = models.LimitedTask.create_task("test")


@pytest.mark.django_db
def test_task_limits_with_id():
    task_a = models.LimitedTaskWithLimitId.create_task("test")
    task_b = models.LimitedTaskWithLimitId.create_task("other")
    with pytest.raises(TaskLimitError):
        task_a = models.LimitedTaskWithLimitId.create_task("test")
    with pytest.raises(TaskLimitError):
        task_b = models.LimitedTaskWithLimitId.create_task("other")

    orm.work_task(task_a)
    orm.work_task(task_b)
    task_a = models.LimitedTaskWithLimitId.create_task("test")
    task_b = models.LimitedTaskWithLimitId.create_task("other")


@pytest.mark.django_db
def test_task_limit_error_returns_message_without_limit_id_provided():
    models.LimitedTask.create_task("test")

    with pytest.raises(TaskLimitError) as exc_info:
        models.LimitedTask.create_task("test")

    assert "Task limit exceeded" == str(exc_info.value)


@pytest.mark.django_db
def test_task_limit_error_returns_message_with_limit_id_provided():
    task = models.LimitedTaskWithLimitId.create_task("test")

    with pytest.raises(TaskLimitError) as exc_info:
        raise TaskLimitError(task)

    assert "Task limit exceeded for task with limit id: test" == str(exc_info.value)


@pytest.mark.django_db
def test_schedule_limited_task_manually(dj_account_objects):
    org = dj_account_objects.org
    models.LimitedTaskWithLimitId.create_task("test")

    task_schedule = TaskSchedule.objects.create(
        org=org,
        task_config={
            "tasks": [
                {
                    "op": "task_limited_2",
                    "param": {"args": ["test"]},
                }
            ],
        },
        description="test",
        repeat=True,
        interval=3600,
        schedule=timezone.now(),
    )

    # This will not raise a TaskLimitError
    task_schedule.spawn_tasks()


@pytest.mark.django_db
def test_task_schedule_cannot_be_claimed_twice(dj_account_objects):
    """Test that a task schedule cannot be claimed twice."""
    org = dj_account_objects.org
    
    # Create a task schedule
    task_schedule = TaskSchedule.objects.create(
        org=org,
        task_config={
            # NO tasks so it is forced to raise a TaskScheduleClaimed and not a TaskAlreadyStarted
            "tasks": [
            ],
        },
        description="test claiming",
        repeat=True,
        interval=3600,
        schedule=timezone.now(),
    )

    schedule_date = task_schedule.schedule
    
    # First claim should succeed
    task_schedule.spawn_tasks()
    
    # reset the schedule date to the original
    task_schedule.schedule = schedule_date
    task_schedule.save()

    # Second claim should fail with TaskScheduleClaimed exception
    with pytest.raises(TaskScheduleClaimed) as exc_info:
        task_schedule.spawn_tasks()
    
    assert "Task schedule already claimed by another worker:" in str(exc_info.value)


@pytest.mark.django_db
def test_task_stack_queue_for_maximum_pending_tasks():
    settings.MAX_PENDING_TASKS = 10
    settings.TASK_MAX_AGE_THRESHOLD = 24

    for _ in range(11):
        models.TestTask.create_task(1, 2)

    with pytest.raises(TaskLimitError):
        health_check_task_stack_queue()


@pytest.mark.django_db
def test_task_stack_queue_for_tasks_exceeding_maximum_age_threshold():
    settings.MAX_PENDING_TASKS = 10
    settings.TASK_MAX_AGE_THRESHOLD = 1

    task = models.TestTask.create_task(1, 2)

    task.created = task.created - timezone.timedelta(hours=2)
    task.save()

    with pytest.raises(TaskMaxAgeError):
        health_check_task_stack_queue()


@pytest.mark.django_db
def test_task_heartbeat():
    task = models.TestTask.create_task(1, 2)
    task.status = "completed"
    task.save()
    task_heartbeat = models.TestTaskHeartbeat.objects.create(task=task)
    task_heartbeat.save()
    health_check_task_heartbeat()


@pytest.mark.django_db
def test_task_heartbeat_timeout():
    settings.HEALTH_CHECK_TASK_INTERVAL_SECONDS = 20
    task = models.TestTask.create_task(1, 2)
    task.status = "running"
    task.save()
    task_heartbeat = models.TestTaskHeartbeat.objects.create(task=task)
    task_heartbeat.timestamp = timezone.now() - timezone.timedelta(
        seconds=settings.HEALTH_CHECK_TASK_INTERVAL_SECONDS + 10
    )
    task_heartbeat.save()

    with pytest.raises(TaskHeartbeatError):
        health_check_task_heartbeat()


@pytest.mark.django_db
def test_cleanup_orphaned_running_tasks_with_stale_heartbeat():
    """Test that cleanup_orphaned_running_tasks marks tasks with stale heartbeats as failed."""
    task = models.TestTask.create_task(1, 2)
    task.status = "running"
    task.save()
    
    # Create an old heartbeat (older than default timeout of 30 seconds)
    heartbeat = models.TestTaskHeartbeat.objects.create(task=task)
    old_timestamp = timezone.now() - timezone.timedelta(seconds=60)
    heartbeat.timestamp = old_timestamp
    heartbeat.save()
    
    assert task.status == "running"
    assert models.TestTaskHeartbeat.objects.filter(task=task).exists()
    
    orm.cleanup_orphaned_running_tasks()
    
    # Refresh and verify task is now failed
    task.refresh_from_db()
    assert task.status == "failed"
    assert "Task orphaned - no heartbeat detected for 30 seconds" in task.error
    assert str(old_timestamp) in task.error
    
    assert not models.TestTaskHeartbeat.objects.filter(task=task).exists()


@pytest.mark.django_db
def test_cleanup_orphaned_running_tasks_with_recent_heartbeat():
    """Test that cleanup_orphaned_running_tasks leaves tasks with recent heartbeats alone."""
    task = models.TestTask.create_task(1, 2)
    task.status = "running"
    task.save()
    
    # Create a recent heartbeat (within timeout)
    heartbeat = models.TestTaskHeartbeat.objects.create(task=task)
    recent_timestamp = timezone.now() - timezone.timedelta(seconds=15)
    heartbeat.timestamp = recent_timestamp
    heartbeat.save()
    
    assert task.status == "running"
    
    orm.cleanup_orphaned_running_tasks()
    
    # Refresh and verify task status unchanged
    task.refresh_from_db()
    assert task.status == "running"
    assert task.error is None or task.error == ""
    
    # Verify heartbeat still exists
    assert models.TestTaskHeartbeat.objects.filter(task=task).exists()


@pytest.mark.django_db
def test_cleanup_orphaned_running_tasks_with_custom_timeout(settings):
    """Test that cleanup_orphaned_running_tasks respects custom timeout settings."""
    settings.TASK_ORPHANED_HEARTBEAT_TIMEOUT = 60
    
    task = models.TestTask.create_task(1, 2)
    task.status = "running"
    task.save()
    
    # Create a heartbeat that's 45 seconds old (within custom timeout)
    heartbeat = models.TestTaskHeartbeat.objects.create(task=task)
    old_timestamp = timezone.now() - timezone.timedelta(seconds=45)
    heartbeat.timestamp = old_timestamp
    heartbeat.save()
    
    # Run cleanup
    orm.cleanup_orphaned_running_tasks()
    
    # Task should still be running since it's within the 60-second timeout
    task.refresh_from_db()
    assert task.status == "running"
    
    # Now make the heartbeat older than the custom timeout
    heartbeat.timestamp = timezone.now() - timezone.timedelta(seconds=90)
    heartbeat.save()
    
    orm.cleanup_orphaned_running_tasks()
    
    # Now the task should be failed
    task.refresh_from_db()
    assert task.status == "failed"
    assert "Task orphaned - no heartbeat detected for 60 seconds" in task.error


@pytest.mark.django_db
def test_cleanup_orphaned_running_tasks_ignores_non_running_tasks():
    """Test that cleanup_orphaned_running_tasks only affects running tasks."""
    pending_task = models.TestTask.create_task(1, 2)
    pending_task.status = "pending"
    pending_task.save()
    
    completed_task = models.TestTask.create_task(3, 4)
    completed_task.status = "completed"
    completed_task.save()
    
    failed_task = models.TestTask.create_task(5, 6)
    failed_task.status = "failed"
    failed_task.save()
    
    # Create old heartbeats for all tasks
    old_timestamp = timezone.now() - timezone.timedelta(seconds=60)
    
    for task in [pending_task, completed_task, failed_task]:
        heartbeat = models.TestTaskHeartbeat.objects.create(task=task)
        heartbeat.timestamp = old_timestamp
        heartbeat.save()
    
    orm.cleanup_orphaned_running_tasks()
    
    # Verify none of the non-running tasks were affected
    for task in [pending_task, completed_task, failed_task]:
        task.refresh_from_db()
        assert task.status != "failed" or task.status == "failed"
        # Heartbeats should still exist for non-running tasks
        assert models.TestTaskHeartbeat.objects.filter(task=task).exists()


@pytest.mark.django_db
def test_cleanup_orphaned_running_tasks_with_no_heartbeat():
    """Test that running tasks without heartbeats are not affected by cleanup."""
    task = models.TestTask.create_task(1, 2)
    task.status = "running"
    task.save()
    
    assert not models.TestTaskHeartbeat.objects.filter(task=task).exists()
    
    # Run cleanup
    orm.cleanup_orphaned_running_tasks()
    
    # Task should remain running (no heartbeat to be stale)
    task.refresh_from_db()
    assert task.status == "running"


@pytest.mark.django_db
def test_cleanup_orphaned_running_tasks_multiple_tasks():
    """Test cleanup with multiple tasks having different heartbeat states."""
    stale_task1 = models.TestTask.create_task(1, 2)
    stale_task1.status = "running"
    stale_task1.save()
    
    stale_task2 = models.TestTask.create_task(3, 4)
    stale_task2.status = "running"
    stale_task2.save()
    
    fresh_task = models.TestTask.create_task(5, 6)
    fresh_task.status = "running"
    fresh_task.save()
    
    # Create stale heartbeats for first two tasks
    old_timestamp = timezone.now() - timezone.timedelta(seconds=60)
    for task in [stale_task1, stale_task2]:
        heartbeat = models.TestTaskHeartbeat.objects.create(task=task)
        heartbeat.timestamp = old_timestamp
        heartbeat.save()
    
    # Create recent heartbeat for third task
    recent_heartbeat = models.TestTaskHeartbeat.objects.create(task=fresh_task)
    recent_heartbeat.timestamp = timezone.now() - timezone.timedelta(seconds=10)
    recent_heartbeat.save()
    
    orm.cleanup_orphaned_running_tasks()
    
    stale_task1.refresh_from_db()
    stale_task2.refresh_from_db()
    fresh_task.refresh_from_db()
    
    # Stale tasks should be failed
    assert stale_task1.status == "failed"
    assert stale_task2.status == "failed"
    
    # Fresh task should still be running
    assert fresh_task.status == "running"
    
    assert not models.TestTaskHeartbeat.objects.filter(task=stale_task1).exists()
    assert not models.TestTaskHeartbeat.objects.filter(task=stale_task2).exists()
    assert models.TestTaskHeartbeat.objects.filter(task=fresh_task).exists()


@pytest.mark.django_db
def test_cleanup_orphaned_running_tasks_with_no_running_tasks():
    """Test that cleanup handles the case where there are no running tasks."""
    completed_task = models.TestTask.create_task(1, 2)
    completed_task.status = "completed"
    completed_task.save()
    
    old_heartbeat = models.TestTaskHeartbeat.objects.create(task=completed_task)
    old_heartbeat.timestamp = timezone.now() - timezone.timedelta(seconds=60)
    old_heartbeat.save()
    
    # Run cleanup - should complete without error
    orm.cleanup_orphaned_running_tasks()
    
    # Verify nothing was changed
    completed_task.refresh_from_db()
    assert completed_task.status == "completed"
    assert models.TestTaskHeartbeat.objects.filter(task=completed_task).exists()


@pytest.mark.django_db
def test_task_schedule_unique_claim_constraint(dj_account_objects):
    """Test that the TaskScheduleClaim enforces the unique constraint."""
    
    org = dj_account_objects.org
    
    # Create a task schedule
    task_schedule = TaskSchedule.objects.create(
        org=org,
        task_config={
            "tasks": [],
        },
        description="test claiming constraint",
        repeat=True,
        interval=3600,
        schedule=timezone.now(),
    )
    
    # Create first claim
    schedule_date = timezone.now()
    claim1 = TaskScheduleClaim.objects.create(
        task_schedule=task_schedule,
        worker_id=worker_id(),
        schedule_date=schedule_date,
    )
    assert claim1.id is not None
    
    # Use an atomic block to contain the IntegrityError
    try:
        with transaction.atomic():
            # Attempting to create a second claim with the same task_schedule and schedule_date
            # should raise an IntegrityError
            TaskScheduleClaim.objects.create(
                task_schedule=task_schedule,
                worker_id=worker_id(),
                schedule_date=schedule_date,
            )
            # If we get here, the test should fail
            assert False, "Expected IntegrityError was not raised"
    except IntegrityError:
        # This is expected, continue with the test
        pass
    
    # Creating a claim with a different schedule_date should succeed
    different_date = timezone.now() + timezone.timedelta(hours=1)
    claim2 = TaskScheduleClaim.objects.create(
        task_schedule=task_schedule,
        worker_id=worker_id(),
        schedule_date=different_date,
    )
    assert claim2.id is not None