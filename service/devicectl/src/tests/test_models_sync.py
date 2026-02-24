from unittest.mock import MagicMock, patch

import django_devicectl.models.devicectl as models
import pytest


@pytest.skip(
    reason="skipping these tests for now, they need to be rewritten",
    allow_module_level=True,
)
class TestSyncVlan:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.vlan = models.Vlan(
            name=None,
            slug=None,
            description=None,
            reference="1",
            facility=None,
            vlan=0,
        )
        self.vlan.save = MagicMock(return_value=True)

        self.patcher = patch(
            "fullctl.django.models.abstract.ServiceBridgeReferenceModel.field_map"
        )
        self.mock_field_map = self.patcher.start()
        self.mock_field_map.return_value = getattr(
            self.vlan.ServiceBridge, "map_netbox"
        )

        self.model = MagicMock()
        self.instance = MagicMock()
        self.netbox_device = MagicMock(
            id=66,
            name="sample netbox device",
            description="sample description",
            site=MagicMock(custom_fields=MagicMock(devicectl_id=None)),
        )

    def teardown(self):
        self.patcher.stop()

    def test_sync_existing_vlan(self):
        self.model.objects.get_or_create.return_value = (
            self.vlan,
            False,
        )
        sync_vlan(
            instance=self.instance,
            netbox_device=self.netbox_device,
            vlan_model=self.model,
        )

        self.vlan.save.assert_called_once()
        self.model.objects.get_or_create.assert_called_once()

        assert self.vlan.description == self.netbox_device.description
        assert self.vlan.name == self.netbox_device.name

    def test_sync_new_vlan(self):
        self.model.objects.get_or_create.return_value = (
            self.vlan,
            True,
        )
        sync_vlan(
            instance=self.instance,
            netbox_device=self.netbox_device,
            vlan_model=self.model,
        )

        self.vlan.save.assert_called_once()
        self.model.objects.get_or_create.assert_called_once()

        assert self.vlan.description == self.netbox_device.description
        assert self.vlan.name == self.netbox_device.name
