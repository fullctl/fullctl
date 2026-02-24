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
        from rest_framework.test import APIClient

        from fullctl.django.auth import permissions
        from fullctl.django.models.concrete import Organization

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

    @property
    def device(self):
        from django_devicectl.models import Device

        if not hasattr(self, "_device"):
            self._device = Device.objects.create(
                instance=self.devicectl_instance,
                name="Test Device",
                description="Sample device test",
                type="ceos",
            )
        return self._device

    @property
    def logical_port(self):
        from django_devicectl.models import LogicalPort

        if not hasattr(self, "_logical_port"):
            self._logical_port = LogicalPort.objects.create(
                instance=self.devicectl_instance,
                name="Test Logical Port",
                description="Sample logical port test",
            )
            self._logical_port.setup(self.devicectl_instance)
        return self._logical_port

    @property
    def physical_port(self):
        from django_devicectl.models import PhysicalPort

        if not hasattr(self, "_physical_port"):
            self._physical_port = PhysicalPort.objects.create(
                device=self.device,
                name="Ethernet1",
                description="Sample physical port test",
                logical_port=self.logical_port,
            )
            self._physical_port.setup(self.devicectl_instance)
        return self._physical_port

    @property
    def physical_ports(self):
        return [self.physical_port]

    @property
    def virtual_port(self):
        return self.logical_port.virtual_ports.first()


def make_account_objects(handle="test"):
    return AccountObjects(handle)


@pytest.fixture
def client_anon():
    from django.test import Client

    return Client()


@pytest.fixture
def account_objects():
    return make_account_objects()
