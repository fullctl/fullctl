import pytest
from django.test import Client

# lazy init for translations
_ = lambda s: s  # noqa: E731


def reset_auto_fields():
    from django.core.management.color import no_style
    from django.db import connection
    from fullctl.django.models.concrete import Organization

    sequence_sql = connection.ops.sequence_reset_sql(no_style(), [Organization])
    with connection.cursor() as cursor:
        for sql in sequence_sql:
            cursor.execute(sql)


class AccountObjects:
    def __init__(self, handle):
        from django.contrib.auth import get_user_model
        from fullctl.django.auth import permissions
        from fullctl.django.models.concrete import Organization, OrganizationUser
        from rest_framework.test import APIClient

        from django_aclctl.models import (
            AccessControlList,
            FilterRule,
            FilterRuleTemplate,
            Instance,
        )

        reset_auto_fields()

        self.user = user = get_user_model().objects.create_user(
            username=f"user_{handle}",
            email=f"{handle}@localhost",
            password="test",
            first_name=f"user_{handle}",
            last_name="last_name",
        )

        self.other_user = get_user_model().objects.create_user(
            username=f"other_user_{handle}",
            email=f"other_{handle}@localhost",
            password="test",
            first_name=f"other_user_{handle}",
            last_name="last_name",
        )

        self.orgs = Organization.sync(
            [
                {"id": 1, "name": f"ORG{handle}", "slug": handle, "personal": True},
                {
                    "id": 2,
                    "name": f"ORG{handle}-2",
                    "slug": f"{handle}-2",
                    "personal": False,
                },
            ],
            user,
            None,
        )

        # add permissions
        user.grainy_permissions.add_permission(self.orgs[0], "crud")
        user.grainy_permissions.add_permission(f"*.{self.orgs[0].id}", "crud")
        user.grainy_permissions.add_permission(f"config.*.{self.orgs[0].id}", "crud")
        user.grainy_permissions.add_permission(self.orgs[1], "r")
        user.grainy_permissions.add_permission(f"*.{self.orgs[1].id}", "r")
        user.grainy_permissions.add_permission(f"config.*.{self.orgs[1].id}", "r")

        self.org = self.orgs[0]

        OrganizationUser.objects.create(org=self.org, user=self.other_user)

        instance = Instance.objects.create(org=self.org)
        self.test_acl = AccessControlList.objects.create(
            instance=instance, name="ACL-test", slug="acl-test"
        )
        self.test_filter_rule = FilterRule.objects.create(
            access_control_list=self.test_acl,
            priority=4,
            src_port=3,
            src_prefix="123.123.123.111",
            dest_port=5,
            dest_prefix="123.123.123.112",
        )

        FilterRuleTemplate.objects.create(instance=instance)

        self.api_client = APIClient()
        self.api_client.login(username=self.user.username, password="test")

        self.client = Client()
        self.client.login(username=user.username, password="test")
        self.perms = permissions(user, refresh=True)


def make_account_objects(handle="test"):
    return AccountObjects(handle)


@pytest.fixture
def account_objects():
    return make_account_objects()
