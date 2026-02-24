import pytest
from account.models import (
    ManagedPermission,
    ManagedPermissionRoleAutoGrant,
    OrganizationManagedPermission,
    OrganizationRole,
    Role,
)
from django.contrib.auth import get_user_model
from django_grainy.util import Permissions
from grainy.const import PERM_CRUD


@pytest.mark.django_db
def test_grant_mode_auto(account_objects, role_objects):
    OrganizationRole.objects.create(
        org=account_objects.org, user=account_objects.user, role=role_objects.test_role
    )

    mperm = ManagedPermission.objects.create(
        namespace="test.mperm",
        status="ok",
        group="test",
        description="test",
        managable=True,
        grant_mode="auto",
    )

    ManagedPermissionRoleAutoGrant.objects.create(
        managed_permission=mperm, role=role_objects.test_role, permissions=PERM_CRUD
    )

    ManagedPermission.apply_roles_all()

    assert Permissions(account_objects.user).check("test.mperm", "r")

    mperm.delete()
    ManagedPermission.apply_roles_all()

    assert not Permissions(account_objects.user).check("test.mperm", "r")


@pytest.mark.django_db
def test_grant_mode_restricted(account_objects, role_objects):
    OrganizationRole.objects.create(
        org=account_objects.org, user=account_objects.user, role=role_objects.test_role
    )

    mperm = ManagedPermission.objects.create(
        namespace="test.mperm",
        status="ok",
        group="test",
        grant_mode="restricted",
        description="test",
        managable=True,
    )

    ManagedPermissionRoleAutoGrant.objects.get_or_create(
        managed_permission=mperm, permissions=PERM_CRUD, role=role_objects.test_role
    )

    ManagedPermission.apply_roles_all()

    assert not Permissions(account_objects.user).check("test.mperm", "r")

    omperm = OrganizationManagedPermission.objects.create(
        org=account_objects.org, managed_permission=mperm, reason="test"
    )

    ManagedPermission.apply_roles_all()

    assert Permissions(account_objects.user).check("test.mperm", "r")

    omperm.delete()

    ManagedPermission.apply_roles_all()

    assert not Permissions(account_objects.user).check("test.mperm", "r")


@pytest.mark.django_db
def test_grant_mode_restricted_add_user(account_objects, role_objects):
    mperm = ManagedPermission.objects.create(
        namespace="test.mperm",
        status="ok",
        group="test",
        grant_mode="restricted",
        description="test",
        managable=True,
    )

    ManagedPermissionRoleAutoGrant.objects.get_or_create(
        managed_permission=mperm, permissions=PERM_CRUD, role=role_objects.test_role
    )

    user_2 = get_user_model().objects.create_user(
        username="user_2", email="user2@localhost", password="user2"
    )

    OrganizationRole.objects.create(
        org=account_objects.org, user=user_2, role=role_objects.test_role
    )

    account_objects.org.add_user(user_2)

    assert not Permissions(user_2).check("test.mperm", "r")

    omperm = OrganizationManagedPermission.objects.create(
        org=account_objects.org, managed_permission=mperm, reason="test"
    )

    ManagedPermission.apply_roles_all()

    assert Permissions(user_2).check("test.mperm", "r")

    omperm.delete()

    ManagedPermission.apply_roles_all()

    assert not Permissions(user_2).check("test.mperm", "r")


@pytest.mark.django_db
def test_grant_mode_restricted_add_user_granted(account_objects, role_objects):
    mperm = ManagedPermission.objects.create(
        namespace="test.mperm",
        status="ok",
        group="test",
        grant_mode="restricted",
        description="test",
        managable=True,
    )

    ManagedPermissionRoleAutoGrant.objects.get_or_create(
        managed_permission=mperm, permissions=PERM_CRUD, role=role_objects.test_role
    )

    user_2 = get_user_model().objects.create_user(
        username="user_2", email="user2@localhost", password="user2"
    )

    OrganizationRole.objects.create(
        org=account_objects.org, user=user_2, role=role_objects.test_role
    )

    omperm = OrganizationManagedPermission.objects.create(
        org=account_objects.org, managed_permission=mperm, reason="test"
    )

    account_objects.org.add_user(user_2)

    ManagedPermission.apply_roles_all()

    assert Permissions(user_2).check("test.mperm", "r")

    omperm.delete()

    ManagedPermission.apply_roles_all()

    assert not Permissions(user_2).check("test.mperm", "r")


class RoleObjects:
    def __init__(self):
        self.test_role = Role.objects.create(
            name="test",
            description="",
            level=15,
            auto_set_on_creator=True,
            auto_set_on_member=False,
        )


@pytest.fixture
def role_objects():
    return RoleObjects()
