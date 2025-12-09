import pytest

from account.social_backends.pipelines import _sync_peeringdb_verified_asns


@pytest.mark.django_db
def test_peeringdb_permissions(account_objects):
    user = account_objects.user

    user.grainy_permissions.add_permission("verified.asn.1234.peeringdb", 15)
    user.grainy_permissions.add_permission("verified.asn.4567.peeringdb", 1)
    user.grainy_permissions.add_permission("verified.asn.72.aaa", 15)

    assert not user.grainy_permissions.filter(
        namespace="verified.asn.63311.peeringdb"
    ).exists()
    assert not user.permission_overrides.exists()

    _sync_peeringdb_verified_asns(
        user,
        [
            {"asn": 63311, "perms": 15},
            {"asn": 4567, "perms": 15},
        ],
    )

    assert (
        user.permission_overrides.filter(
            namespace="verified.asn.63311.peeringdb"
        ).count()
        == 1
    )
    assert (
        user.permission_overrides.filter(
            namespace="verified.asn.4567.peeringdb"
        ).count()
        == 1
    )
    assert user.permission_overrides.count() == 2

    assert user.grainy_permissions.filter(
        namespace="verified.asn.63311.peeringdb", permission=15
    ).exists()
    assert user.grainy_permissions.filter(
        namespace="verified.asn.4567.peeringdb", permission=15
    ).exists()
    assert user.grainy_permissions.filter(
        namespace="verified.asn.72.aaa", permission=15
    ).exists()
    assert not user.grainy_permissions.filter(
        namespace="verified.asn.1234.peeringdb"
    ).exists()
