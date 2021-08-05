import pytest


import fullctl.django.tasks.orm as orm

import tests.django_tests.testapp.models as models

@pytest.mark.django_db
def test_fetch_tasks():

    task = models.TestTask.create_task(1,2)
    assert task == orm.fetch_task()

@pytest.mark.django_db
def test_work_tasks():

    task = models.TestTask.create_task(1,2)

    orm.claim_task(task)

    assert task.queue_id
    assert task.taskclaim

    orm.work_task(task)

    assert task.status == "completed"
    assert int(task.output) == 3

@pytest.mark.django_db
def test_parent_task():

    task_par = models.TestTask.create_task(1,2)
    task_chl = models.TestTask.create_task(7,3,parent=task_par)

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










