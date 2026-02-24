import django_auditctl.models as models
import pytest
from django.contrib.auth import get_user_model
from django.test import TestCase
from django_auditctl.rest.views.auditctl import handle_info_status

from fullctl.django.models import Organization

User = get_user_model()

# The object 'Event' from 'django_auditctl.models' has no 'DoesNotExist' member
# This is a common issue with Django models and linters.
# The DoesNotExist exception is added dynamically by Django's ORM.
# We can tell pylint to ignore this.
# pylint: disable=no-member


@pytest.mark.django_db
class TestHandleInfoStatus(TestCase):
    """Test the handle_info_status function using the test database"""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser", email="test@example.com", password="testpassword"
        )
        self.org = Organization.objects.create(name="Test Org", slug="test-org")

    def test_handle_info_status_success(self):
        """Test successful update of existing event"""
        existing_event = models.Event.objects.create(
            object_id="v1/test-org/device/123",
            org=self.org,
            user=self.user,
            status="ok",
            data={
                "name": "Device 123",
                "components": [{"id": "comp1"}],
            },
        )

        update_data = {
            "data": {
                "status": "maintenance",
                "components": [{"id": "comp2"}],
            }
        }

        success, event, error_message = handle_info_status(
            self.org, "v1/test-org/device/123", update_data
        )

        assert success is True
        assert error_message is None

        # Refresh from db to get the updated data
        existing_event.refresh_from_db()

        assert event.id == existing_event.id
        assert existing_event.data["name"] == "Device 123"  # Unchanged
        assert existing_event.data["status"] == "maintenance"  # Overwritten
        assert len(existing_event.data["components"]) == 2

    def test_handle_info_status_no_existing_event(self):
        """Test when no existing event is found"""
        update_data = {"data": {"status": "active"}}

        success, event, error_message = handle_info_status(
            self.org, "v1/test-org/device/456", update_data
        )

        assert success is False
        assert event is None
        assert "No existing event found" in error_message

    def test_handle_info_status_empty_data(self):
        """Test with empty data field"""
        initial_data = {"name": "Device 789"}
        existing_event = models.Event.objects.create(
            object_id="v1/test-org/device/789",
            org=self.org,
            user=self.user,
            status="ok",
            data=initial_data.copy(),
        )

        # Call with no 'data' key
        success, _, _ = handle_info_status(self.org, "v1/test-org/device/789", {})

        existing_event.refresh_from_db()
        assert success is True
        assert existing_event.data == initial_data

        # Call with empty 'data' dict
        success, _, _ = handle_info_status(
            self.org, "v1/test-org/device/789", {"data": {}}
        )

        existing_event.refresh_from_db()
        assert success is True
        assert existing_event.data == initial_data
