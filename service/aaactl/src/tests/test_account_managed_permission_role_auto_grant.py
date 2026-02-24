import pytest
import reversion
from account.models import (
    ManagedPermission,
    ManagedPermissionRoleAutoGrant,
    OrganizationRole,
    Role,
    UpdatePermissions,
)
from django_grainy.util import Permissions
from grainy.const import PERM_CRUD


@pytest.mark.django_db
def test_managed_permission_role_auto_grant_add_and_delete(account_objects):
    test_role = Role.objects.create(
        name="test",
        description="",
        level=15,
        auto_set_on_creator=True,
        auto_set_on_member=False,
    )

    OrganizationRole.objects.create(
        org=account_objects.org, user=account_objects.user, role=test_role
    )

    mperm = ManagedPermission.objects.create(
        namespace="test.mperm",
        status="ok",
        group="test",
        description="test",
        managable=True,
        grant_mode="auto",
    )

    update_permissions_count = UpdatePermissions.objects.count()
    with reversion.create_revision():
        mpermroleautogrant = ManagedPermissionRoleAutoGrant.objects.create(
            managed_permission=mperm, role=test_role, permissions=PERM_CRUD
        )

    assert update_permissions_count + 1 == UpdatePermissions.objects.count()

    UpdatePermissions.objects.last()._run()

    assert Permissions(account_objects.user).check("test.mperm", "r")

    update_permissions_count = UpdatePermissions.objects.count()
    mpermroleautogrant.delete()

    assert update_permissions_count + 1 == UpdatePermissions.objects.count()

    UpdatePermissions.objects.last()._run()

    assert not Permissions(account_objects.user).check("test.mperm", "r")
