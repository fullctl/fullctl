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
            f"service.pdbctl.{self.orgs[0].id}", "crud"
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


def make_account_objects(handle="test"):
    return AccountObjects(handle)


@pytest.fixture
def client_anon():
    from django.test import Client

    return Client()


@pytest.fixture
def account_objects():
    return make_account_objects()


@pytest.fixture
def pdb_data():
    from django_peeringdb.models.concrete import (
        Facility,
        InternetExchange,
        IXLan,
        Network,
        Organization,
    )

    org = Organization.objects.create(name="Org", status="ok")
    net = Network.objects.create(name="Net", status="ok", asn=63311, org=org)
    net_2 = Network.objects.create(name="Net 2", status="ok", asn=63312, org=org)
    fac = Facility.objects.create(name="Fac", status="ok", org=org)
    ix = InternetExchange.objects.create(name="Exchange", status="ok", org=org)
    ixlan = IXLan.objects.create(mtu=1500, ix=ix, status="ok")

    return {
        "org": org,
        "net": net,
        "net_2": net_2,
        "ix": ix,
        "fac": fac,
        "ixlan": ixlan,
    }
