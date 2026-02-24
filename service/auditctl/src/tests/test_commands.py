import os

import pytest
from django.core import management
from django_auditctl.models import Event


def assert_json_file(dir_path: str):
    # checks the first .json file in the directory
    # and loads it

    json_file = None
    for file in os.listdir(dir_path):
        if file.endswith(".json"):
            json_file = file
            break

    assert json_file is not None

    with open(os.path.join(dir_path, json_file)) as f:
        data = f.read()
        assert data is not None


@pytest.mark.django_db
def test_auditctl_prune_old_events_command_no_old_events(tmp_path):
    Event.objects.create()
    management.call_command(
        "auditctl_prune", max_age=1, commit=True, output_path=str(tmp_path)
    )
    assert Event.objects.count() == 1


@pytest.mark.django_db
def test_run_auditctl_prune_old_events_command_events_available_old_events(tmp_path):
    Event.objects.create()  # Create a first event
    Event.objects.create()  # Create a second event
    management.call_command(
        "auditctl_prune", max_age=0, commit=True, output_path=str(tmp_path)
    )
    assert Event.objects.count() == 0
    assert_json_file(str(tmp_path))


@pytest.mark.django_db
def test_run_auditctl_prune_some_old_events(tmp_path):
    Event.objects.create()
    event_old = Event.objects.create()
    # backdate
    event_old.created = event_old.created.replace(year=2019)
    event_old.save()

    management.call_command(
        "auditctl_prune", max_age=1, commit=True, output_path=str(tmp_path)
    )

    assert Event.objects.count() == 1
    assert_json_file(str(tmp_path))


@pytest.mark.django_db
def test_run_auditctl_prune_old_events_pretend_mode(tmp_path):
    Event.objects.create()  # Create a first event
    Event.objects.create()  # Create a second event
    management.call_command("auditctl_prune", max_age=0, output_path=str(tmp_path))

    assert Event.objects.count() == 2
