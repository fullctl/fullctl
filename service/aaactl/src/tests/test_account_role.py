import pytest
from account.models import (
    ManagedPermission,
    ManagedPermissionRoleAutoGrant,
    OrganizationRole,
    Role,
)
from django.db.models.deletion import ProtectedError
from django_grainy.util import Permissions
from grainy.const import PERM_CRUD


@pytest.mark.django_db
def test_organization_role_add_and_delete(account_objects):
    test_role = Role.objects.create(
        name="test",
        description="",
        level=15,
        auto_set_on_creator=True,
        auto_set_on_member=False,
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
        managed_permission=mperm, role=test_role, permissions=PERM_CRUD
    )

    org_role = OrganizationRole.objects.create(
        org=account_objects.org, user=account_objects.user, role=test_role
    )
    ManagedPermission.apply_roles_all()

    with pytest.raises(
        ProtectedError,
        match="Cannot delete some instances of model 'Role' because they are referenced through protected foreign keys",
    ):
        test_role.delete()

    org_role.delete()
    test_role.delete()

    assert not Permissions(account_objects.user).check("test.mperm", "r")
