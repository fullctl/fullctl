import json
from importlib import import_module

from django.conf import settings
from django.middleware.csrf import CSRF_SESSION_KEY


def mock_csrf_session(request):
    engine = import_module(settings.SESSION_ENGINE)
    request.session = engine.SessionStore("deadbeef")
    request.session[CSRF_SESSION_KEY] = "csrf-session-key"
    request._dont_enforce_csrf_checks = True


def set_assert_field_exists(field, data):
    if field in data:
        data[field] = "assert-field-exists"


def strip_api_fields(data):
    """
    created and updated fields will change with every test run
    so strip them out
    """
    if isinstance(data, dict):
        values = data.values()
    elif isinstance(data, list):
        values = data

    for v in values:
        if isinstance(v, dict):
            v.pop("created", None)
            v.pop("updated", None)
            set_assert_field_exists("org_id", v)
            set_assert_field_exists("org_user", v)
            set_assert_field_exists("org", v)
            set_assert_field_exists("billing_contact", v)
            set_assert_field_exists("group", v)
            set_assert_field_exists("user", v)
            set_assert_field_exists("id", v)
            set_assert_field_exists("role", v)
            strip_api_fields(v)
        if isinstance(v, list):
            strip_api_fields(v)
    return data


def assert_expected(response, expected):
    assert response.status_code == expected["status"]
    if isinstance(expected["response"], dict):
        print("RSP")
        print(json.dumps(strip_api_fields(response.json()), indent=2))
        print("EXP")
        print(json.dumps(strip_api_fields(expected), indent=2))
        assert strip_api_fields(response.json()) == strip_api_fields(
            expected["response"]
        )
    else:
        print(response.content.decode("utf-8"))
        assert response.content.decode("utf-8") == expected["response"]
