import pytest


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
        from django.test import Client
        from fullctl.django.auth import permissions
        from fullctl.django.models.concrete import Organization
        from rest_framework.test import APIClient

        reset_auto_fields()

        self.user = user = get_user_model().objects.create_user(
            username=f"user_{handle}",
            email=f"{handle}@localhost",
            password="test",
            first_name=f"user_{handle}",
            last_name="last_name",
        )

        self.orgs = Organization.sync(
            [
                {"id": 1, "name": f"ORG{handle}", "slug": handle, "personal": True},
            ],
            user,
            None,
        )

        # add permissions
        user.grainy_permissions.add_permission(
            f"service.devicectl.{self.orgs[0].id}", "crud"
        )
        user.grainy_permissions.add_permission(self.orgs[0], "crud")
        user.grainy_permissions.add_permission(f"*.{self.orgs[0].id}", "crud")
        user.grainy_permissions.add_permission("service_bridge", "r")

        self.org = self.orgs[0]

        self.api_client = APIClient()
        self.api_client.login(username=user.username, password="test")

        self.client = Client()
        self.client.login(username=user.username, password="test")
        self.perms = permissions(user, refresh=True)

    @property
    def devicectl_instance(self):
        from django_devicectl.models import Instance

        if not hasattr(self, "_devicectl_instance"):
            self._devicectl_instance = Instance.objects.create(org=self.org)
        return self._devicectl_instance

    @property
    def facility(self):
        from django_devicectl.models import Facility

        if not hasattr(self, "_facility"):
            self._facility = Facility.objects.create(
                instance=self.devicectl_instance,
                name="Test Facility",
                slug="test_faciility",
            )
        return self._facility

    @property
    def vlan(self):
        from django_devicectl.models import Vlan

        if not hasattr(self, "_vlan"):
            self._vlan = Vlan.objects.create(
                instance=self.devicectl_instance,
                facility=self.facility,
                name="Test Vlan",
                vlan=12,
                slug="test_vlan",
                description="Sample Vlan test",
            )
        return self._vlan


def make_account_objects(handle="test"):
    return AccountObjects(handle)


@pytest.fixture
def client_anon():
    from django.test import Client

    return Client()


@pytest.fixture
def account_objects():
    return make_account_objects()
