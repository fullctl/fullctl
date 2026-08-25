import json
import os

import pytest
from django.core import management
from django.core.management.base import CommandError
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
    parsed = json.loads(data)
    assert isinstance(parsed, list)


def make_old_event(**kwargs):
    """Create an event backdated to 2019."""
    event = Event.objects.create(**kwargs)
    event.created = event.created.replace(year=2019)
    event.save()
    return event


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
        "auditctl_prune", max_age=0, commit=True, output_path=str(tmp_path), backup=True
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
        "auditctl_prune", max_age=1, commit=True, output_path=str(tmp_path), backup=True
    )

    assert Event.objects.count() == 1
    assert_json_file(str(tmp_path))


@pytest.mark.django_db
def test_run_auditctl_prune_old_events_pretend_mode(tmp_path):
    Event.objects.create()  # Create a first event
    Event.objects.create()  # Create a second event
    management.call_command("auditctl_prune", max_age=0, output_path=str(tmp_path))

    assert Event.objects.count() == 2


# --- include / exclude tests ---


@pytest.mark.django_db
def test_run_auditctl_prune_include_pattern(tmp_path):
    """Only events whose object_id matches --include are deleted."""
    make_old_event(object_id="v0.1/org-1/config/liveness/")
    make_old_event(object_id="v0.1/org-2/config/liveness/")
    make_old_event(object_id="v0.1/org-1/config/readiness/")

    management.call_command(
        "auditctl_prune",
        max_age=1,
        commit=True,
        output_path=str(tmp_path),
        include="v0.1/.+/config/liveness/",
    )

    remaining = list(Event.objects.values_list("object_id", flat=True))
    assert remaining == ["v0.1/org-1/config/readiness/"]


@pytest.mark.django_db
def test_run_auditctl_prune_exclude_pattern(tmp_path):
    """Events whose object_id matches --exclude are kept; others are deleted."""
    make_old_event(object_id="v0.1/org-1/config/liveness/")
    make_old_event(object_id="v0.1/org-2/config/liveness/")
    make_old_event(object_id="v0.1/org-1/config/readiness/")

    management.call_command(
        "auditctl_prune",
        max_age=1,
        commit=True,
        output_path=str(tmp_path),
        exclude="v0.1/.+/config/liveness/",
    )

    remaining = list(Event.objects.values_list("object_id", flat=True))
    assert sorted(remaining) == sorted(
        ["v0.1/org-1/config/liveness/", "v0.1/org-2/config/liveness/"]
    )


@pytest.mark.django_db
def test_run_auditctl_prune_include_wildcard(tmp_path):
    """Bare * in --include is expanded to .* (glob-style wildcard)."""
    make_old_event(object_id="v0.1/org-1/config/liveness/")
    make_old_event(object_id="v0.1/org-2/config/liveness/")
    make_old_event(object_id="v0.1/org-1/config/readiness/")

    management.call_command(
        "auditctl_prune",
        max_age=1,
        commit=True,
        output_path=str(tmp_path),
        include="v0.1/*/config/liveness/",
    )

    remaining = list(Event.objects.values_list("object_id", flat=True))
    assert remaining == ["v0.1/org-1/config/readiness/"]


@pytest.mark.django_db
def test_run_auditctl_prune_include_no_match(tmp_path):
    """--include pattern that matches nothing leaves all events intact."""
    make_old_event(object_id="v0.1/org-1/config/readiness/")

    management.call_command(
        "auditctl_prune",
        max_age=1,
        commit=True,
        output_path=str(tmp_path),
        include="v99/.+/nomatch/",
    )

    assert Event.objects.count() == 1
    # no JSON file should be written when the queryset is empty
    assert not any(f.endswith(".json") for f in os.listdir(str(tmp_path)))


# pattern_to_regex itself is unit-tested in fullctl core
# (tests/django_tests/test_commands.py); only its use from this command is
# covered here.


@pytest.mark.django_db
def test_run_auditctl_prune_invalid_include_pattern(tmp_path):
    """Invalid regex in --include raises CommandError."""
    make_old_event(object_id="v0.1/org-1/config/liveness/")
    with pytest.raises(CommandError, match="Invalid regex for --include"):
        management.call_command(
            "auditctl_prune",
            max_age=1,
            commit=True,
            output_path=str(tmp_path),
            include="[invalid",
        )


@pytest.mark.django_db
def test_run_auditctl_prune_invalid_exclude_pattern(tmp_path):
    """Invalid regex in --exclude raises CommandError."""
    make_old_event(object_id="v0.1/org-1/config/liveness/")
    with pytest.raises(CommandError, match="Invalid regex for --exclude"):
        management.call_command(
            "auditctl_prune",
            max_age=1,
            commit=True,
            output_path=str(tmp_path),
            exclude="[invalid",
        )
