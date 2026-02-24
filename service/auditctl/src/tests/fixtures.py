import pytest
from django.test import Client

import fullctl.django.testutil as testutil

# lazy init for translations
_ = lambda s: s  # noqa: E731


class AccountObjects(testutil.AccountObjects):
    @property
    def auditctl_instance(self):
        from django_auditctl.models import Instance

        if not hasattr(self, "_auditctl_instance"):
            self._auditctl_instance = Instance.objects.create(org=self.org)

        return self._auditctl_instance


def make_account_objects(handle="test"):
    return AccountObjects(handle)


@pytest.fixture
def client_anon():
    return Client()


@pytest.fixture
def account_objects():
    return make_account_objects()


@pytest.fixture
def account_objects_b():
    return make_account_objects("test_b")
