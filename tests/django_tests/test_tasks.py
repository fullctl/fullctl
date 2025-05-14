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