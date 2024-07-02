import pytest

from django.contrib.auth import get_user_model
from django.core import management
from django.http import HttpRequest
from django.urls import reverse

from account.impersonate import is_impersonating, start_impersonation, allowed_to_impersonate
from account.models import Impersonation
from tests.helpers import mock_csrf_session


def test_start_impersontation(db, account_objects, account_objects_b):
    management.call_command("fullctl_promote_user", "user_test", "--commit")
    user = get_user_model().objects.get(username="user_test")

    request = HttpRequest()
    request.method = "GET"
    request.user = user
    mock_csrf_session(request)
    impersontation_count = Impersonation.objects.count()

    start_impersonation(request, account_objects_b.user)
    assert Impersonation.objects.count() == impersontation_count + 1

    response = account_objects.client.get(
        reverse("account:controlpanel"),
    )
    assert (
        "Currently impersonating <b>" + account_objects_b.user.username + "</b>"
        in str(response.content)
    )


def test_is_impersontating(db, account_objects, account_objects_b):
    management.call_command("fullctl_promote_user", "user_test", "--commit")
    user = get_user_model().objects.get(username="user_test")

    request = HttpRequest()
    request.method = "GET"
    request.user = user
    mock_csrf_session(request)
    start_impersonation(request, account_objects_b.user)

    assert is_impersonating(request) == account_objects_b.user


def test_stop_impersontation(db, account_objects, account_objects_b):
    management.call_command("fullctl_promote_user", "user_test", "--commit")
    User = get_user_model()
    user = User.objects.get(username="user_test")

    request = HttpRequest()
    request.method = "GET"
    request.user = user
    mock_csrf_session(request)
    start_impersonation(request, account_objects_b.user)

    assert account_objects_b.user == is_impersonating(request)

    account_objects.client.get(
        reverse("admin:auth_user_actions", args=(user.id, "stop_impersonation"))
    )

    user = User.objects.get(username="user_test")
    request.user = user

    assert is_impersonating(request) is None


def test_impersonate_permission(db, account_objects, account_objects_b):
    # check that user starts off as a non superuser
    assert not account_objects.user.is_superuser

    # add impersonate permissions to user
    account_objects.user.grainy_permissions.add_permission("impersonate", "c")

    # check that the user can impersonate
    request = HttpRequest()

    request.method = "GET"
    request.user = account_objects.user
    mock_csrf_session(request)
    start_impersonation(request, account_objects_b.user)

    assert is_impersonating(request) == account_objects_b.user

def test_only_superuser_can_impersonate_superuser(db, account_objects, account_objects_b):
    # check that user starts off as a non superuser
    assert not account_objects.user.is_superuser

    # add impersonate permissions to user
    account_objects.user.grainy_permissions.add_permission("impersonate", "c")

    # now promote user b to superuser
    account_objects_b.user.is_superuser = True
    account_objects_b.user.save()

    # check that the user can not impersonate since user b is a superuser
    # and user a is not a superuser
    request = HttpRequest()
    request.method = "GET"
    request.user = account_objects.user
    mock_csrf_session(request)
    
    start_impersonation(request, account_objects_b.user)

    assert is_impersonating(request) is None

    # now promote user a to superuser

    account_objects.user.is_superuser = True
    account_objects.user.save()

    # check that the user can impersonate

    request = HttpRequest()
    request.method = "GET"
    request.user = account_objects.user

    mock_csrf_session(request)

    start_impersonation(request, account_objects_b.user)

    assert is_impersonating(request) == account_objects_b.user

@pytest.mark.parametrize(
    "user_a_is_superuser, user_a_has_permissions, user_b_is_superuser, expected",
    [
        # success
        (True, True, False, True),
        (True, False, False, True),
        (True, True, True, True),
        (True, False, True, True),
        (False, True, False, True),
        # no success case
        (False, False, False, False),
        (False, False, True, False),
        (False, True, True, False),
    ],
)
def test_allowed_to_impersonate(db, account_objects, account_objects_b, user_a_is_superuser, user_a_has_permissions, user_b_is_superuser, expected):
    account_objects.user.is_superuser = user_a_is_superuser
    account_objects.user.save()

    account_objects_b.user.is_superuser = user_b_is_superuser
    account_objects_b.user.save()

    if user_a_has_permissions:
        account_objects.user.grainy_permissions.add_permission("impersonate", "c")

    assert allowed_to_impersonate(account_objects.user, account_objects_b.user) == expected