import pytest
from django.utils import timezone

import fullctl.django.tasks.orm as orm
import tests.django_tests.testapp.models as models
from fullctl.django.models.concrete.tasks import TaskClaimed, TaskLimitError, TaskSchedule


@pytest.mark.django_db
def test_task_with_max_run_time():
    task = models.TestTaskWithMaxRunTime.create_task(1, 2)

    orm.work_task(task)

    task.created = task.created - timezone.timedelta(hours=2)
    task.save()

    orm.tasks_max_time_reached(task)

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
                    "param": {
                        "args": ["test"]
                    },
                }
            ],
        },
        description="test",
        repeat=True,
        interval=3600,
        schedule=timezone.now(),
    )
    
    task_schedule.spawn_tasks()
