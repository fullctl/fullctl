import pytest
from django.test import RequestFactory
from django_grainy.util import Permissions

import fullctl.django.templatetags.fullctl_util as fullctl_util


@pytest.fixture
def test_request(db, dj_account_objects):
    request = RequestFactory().get("/test")
    request.org = dj_account_objects.org
    return request


def test_can_read(db, dj_account_objects, test_request):
    request = test_request
    user = dj_account_objects.user
    user.grainy_permissions.add_permission_set({"org.1": "c"})
    request.perms = Permissions(user)

    assert fullctl_util.can_read(request, "org.1") is False

    user.grainy_permissions.add_permission_set({"org.1": "r"})
    request.perms = Permissions(user)

    assert fullctl_util.can_read(request, "org.1") is True


def test_can_create(db, dj_account_objects, test_request):
    request = test_request
    user = dj_account_objects.user
    user.grainy_permissions.add_permission_set({"org.1": "rud"})
    request.perms = Permissions(user)

    assert fullctl_util.can_create(request, "org.1") is False

    user.grainy_permissions.add_permission_set({"org.1": "crud"})
    request.perms = Permissions(user)

    assert fullctl_util.can_create(request, "org.1") is True


def test_can_update(db, dj_account_objects, test_request):
    request = test_request
    user = dj_account_objects.user
    user.grainy_permissions.add_permission_set({"org.1": "rd"})
    request.perms = Permissions(user)

    assert fullctl_util.can_update(request, "org.1") is False

    user.grainy_permissions.add_permission_set({"org.1": "rud"})
    request.perms = Permissions(user)

    assert fullctl_util.can_update(request, "org.1") is True


def test_can_delete(db, dj_account_objects, test_request):
    request = test_request
    user = dj_account_objects.user
    user.grainy_permissions.add_permission_set({"org.1": "r"})
    request.perms = Permissions(user)

    assert fullctl_util.can_delete(request, "org.1") is False

    user.grainy_permissions.add_permission_set({"org.1": "cud"})
    request.perms = Permissions(user)

    assert fullctl_util.can_delete(request, "org.1") is True
