from collections import namedtuple

import pytest
from account.models import (
    ManagedPermission,
    ManagedPermissionRoleAutoGrant,
    Organization,
    OrganizationManagedPermission,
    OrganizationRole,
    OrganizationUser,
    Role,
)
from django_grainy.util import Permissions
from grainy.const import PERM_CRUD


@pytest.fixture
def multi_org_user(db, account_objects):
    """
    Sets up a user that is a member of two organizations
    """
    user = account_objects.user
    org_a = account_objects.org

    # create a second organization and add the user
    org_b = Organization.objects.create(name="Org B")
    org_b.add_user(user)

    # ensure user is in org_a too, since the account_objects
    # fixture does not guarantee that
    if not OrganizationUser.objects.filter(org=org_a, user=user).exists():
        org_a.add_user(user)

    # setup roles
    role_a = Role.objects.create(name="Role A", level=10)
    role_b = Role.objects.create(name="Role B", level=10)

    # setup managed permissions
    mperm_a = ManagedPermission.objects.create(
        namespace="test.a.{org_id}",
        group="test",
        description="Permission A",
        grant_mode="auto",
    )
    mperm_b = ManagedPermission.objects.create(
        namespace="test.b.{org_id}",
        group="test",
        description="Permission B",
        grant_mode="auto",
    )

    # setup role grants
    ManagedPermissionRoleAutoGrant.objects.create(
        managed_permission=mperm_a, role=role_a, permissions=PERM_CRUD
    )
    ManagedPermissionRoleAutoGrant.objects.create(
        managed_permission=mperm_b, role=role_b, permissions=PERM_CRUD
    )

    # clear all permissions to start from a clean state
    user.grainy_permissions.all().delete()

    Objects = namedtuple(
        "Objects",
        ["user", "org_a", "org_b", "role_a", "role_b", "mperm_a", "mperm_b"],
    )
    return Objects(
        user=user,
        org_a=org_a,
        org_b=org_b,
        role_a=role_a,
        role_b=role_b,
        mperm_a=mperm_a,
        mperm_b=mperm_b,
    )


@pytest.mark.django_db
def test_add_role_in_one_org(multi_org_user):
    """
    Test that adding a role in one org grants permissions for that org
    without affecting the other.
    """
    u = multi_org_user
    perm_a = u.mperm_a.namespace.format(org_id=u.org_a.id)
    perm_b = u.mperm_b.namespace.format(org_id=u.org_b.id)

    # user has role in org_b but not org_a
    OrganizationRole.objects.create(org=u.org_b, user=u.user, role=u.role_b)
    ManagedPermission.apply_roles(u.org_b, u.user)

    assert not Permissions(u.user).check(perm_a, "r")
    assert Permissions(u.user).check(perm_b, "r")

    # add role in org_a
    OrganizationRole.objects.create(org=u.org_a, user=u.user, role=u.role_a)
    ManagedPermission.apply_roles(u.org_a, u.user)

    assert Permissions(u.user).check(perm_a, "r")
    assert Permissions(u.user).check(perm_b, "r")


@pytest.mark.django_db
def test_remove_role_in_one_org(multi_org_user):
    """
    Test that removing a role in one org revokes permissions for that org
    without affecting the other.
    """

    u = multi_org_user
    perm_a = u.mperm_a.namespace.format(org_id=u.org_a.id)
    perm_b = u.mperm_b.namespace.format(org_id=u.org_b.id)

    # user has roles in both orgs
    OrganizationRole.objects.create(org=u.org_a, user=u.user, role=u.role_a)
    OrganizationRole.objects.create(org=u.org_b, user=u.user, role=u.role_b)
    ManagedPermission.apply_roles(u.org_a, u.user)

    assert Permissions(u.user).check(perm_a, "r")
    assert Permissions(u.user).check(perm_b, "r")

    # remove role from org_a
    OrganizationRole.objects.get(org=u.org_a, user=u.user, role=u.role_a).delete()
    ManagedPermission.apply_roles(u.org_a, u.user)

    assert not Permissions(u.user).check(perm_a, "r")
    assert Permissions(u.user).check(perm_b, "r")


@pytest.mark.django_db
def test_add_restricted_permission_to_org(multi_org_user):
    """
    Test that for a restricted permission, granting it to an org gives the user
    the permission, without affecting other orgs.
    """
    u = multi_org_user
    perm_a = u.mperm_a.namespace.format(org_id=u.org_a.id)
    perm_b = u.mperm_b.namespace.format(org_id=u.org_b.id)

    u.mperm_a.grant_mode = "restricted"
    u.mperm_a.save()

    # user has roles in both orgs
    OrganizationRole.objects.create(org=u.org_a, user=u.user, role=u.role_a)
    OrganizationRole.objects.create(org=u.org_b, user=u.user, role=u.role_b)
    ManagedPermission.apply_roles(u.org_a, u.user)

    # permission a is not granted because it is restricted
    assert not Permissions(u.user).check(perm_a, "r")
    assert Permissions(u.user).check(perm_b, "r")

    # grant org_a access to restricted permission
    OrganizationManagedPermission.objects.create(
        org=u.org_a, managed_permission=u.mperm_a
    )
    ManagedPermission.apply_roles_org(u.org_a)

    assert Permissions(u.user).check(perm_a, "r")
    assert Permissions(u.user).check(perm_b, "r")


@pytest.mark.django_db
def test_remove_restricted_permission_from_org(multi_org_user):
    """
    Test that for a restricted permission, revoking it from an org removes the
    user's permission, without affecting other orgs.
    """
    u = multi_org_user
    perm_a = u.mperm_a.namespace.format(org_id=u.org_a.id)
    perm_b = u.mperm_b.namespace.format(org_id=u.org_b.id)

    u.mperm_a.grant_mode = "restricted"
    u.mperm_a.save()

    # grant org_a access to restricted permission
    OrganizationManagedPermission.objects.create(
        org=u.org_a, managed_permission=u.mperm_a
    )

    # user has roles in both orgs
    OrganizationRole.objects.create(org=u.org_a, user=u.user, role=u.role_a)
    OrganizationRole.objects.create(org=u.org_b, user=u.user, role=u.role_b)

    ManagedPermission.apply_roles_org(u.org_a)
    ManagedPermission.apply_roles_org(u.org_b)

    assert Permissions(u.user).check(perm_a, "r")
    assert Permissions(u.user).check(perm_b, "r")

    # revoke org_a access to restricted permission
    OrganizationManagedPermission.objects.get(
        org=u.org_a, managed_permission=u.mperm_a
    ).delete()
    ManagedPermission.apply_roles_org(u.org_a)

    assert not Permissions(u.user).check(perm_a, "r")
    assert Permissions(u.user).check(perm_b, "r")


@pytest.mark.django_db
def test_org_agnostic_namespace_permission(multi_org_user):
    """
    Test that permissions on org-agnostic namespaces are handled
    correctly when a user is in multiple orgs.
    """
    u = multi_org_user
    perm_agnostic = "verified.asn.63311.aaa"

    # create org-agnostic managed permission and grant it to role_a
    mperm_agnostic = ManagedPermission.objects.create(
        namespace=perm_agnostic,
        group="test",
        description="Agnostic Permission",
        grant_mode="auto",
    )
    ManagedPermissionRoleAutoGrant.objects.create(
        managed_permission=mperm_agnostic, role=u.role_a, permissions=PERM_CRUD
    )

    # sanity check: user should not have the permission yet
    assert not Permissions(u.user).check(perm_agnostic, "r")

    # assign role_a in org_a -> user gets permission
    org_role_a = OrganizationRole.objects.create(
        org=u.org_a, user=u.user, role=u.role_a
    )
    ManagedPermission.apply_roles(u.org_a, u.user)

    assert Permissions(u.user).check(perm_agnostic, "r")

    # assign role_a in org_b as well
    org_role_b = OrganizationRole.objects.create(
        org=u.org_b, user=u.user, role=u.role_a
    )
    ManagedPermission.apply_roles(u.org_b, u.user)

    assert Permissions(u.user).check(perm_agnostic, "r")

    # remove role from org_a -> user should still have permission through org_b
    org_role_a.delete()
    ManagedPermission.apply_roles(u.org_a, u.user)

    assert Permissions(u.user).check(perm_agnostic, "r")

    # remove role from org_b -> user should now lose the permission
    org_role_b.delete()
    ManagedPermission.apply_roles(u.org_b, u.user)

    assert not Permissions(u.user).check(perm_agnostic, "r")
