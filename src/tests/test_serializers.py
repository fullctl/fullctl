import pytest
from rest_framework.test import APIRequestFactory

from django_auditctl.models import Event
from django_auditctl.rest.serializers.auditctl import Serializers
from tests.fixtures import account_objects  # noqa: F401


@pytest.mark.django_db
class TestEventSerializer:
    """Test the Event serializer's backwards compatible error handling"""

    def test_error_in_error_field_legacy_behavior(self, account_objects):
        """Test that sending error info in the 'error' field works (legacy behavior)"""
        error_data = {
            "message": "Test error message",
            "components": [
                {
                    "name": "test-component",
                    "kind": "device",
                    "error": "Component error"
                }
            ]
        }
        
        data = {
            "object_id": "v0.1/test/config/device/test123",
            "status": "error",
            "error": error_data,
            "org": account_objects.org.id,
            "user": account_objects.user.id
        }
        
        serializer = Serializers.event(data=data, context={"object_id": "v0.1/test/config/device/test123"})
        assert serializer.is_valid()
        
        # Save and retrieve
        event = serializer.save()
        
        # Verify data was saved correctly
        assert event.status == "error"
        # Check that the essential fields are present (pydantic adds extra fields)
        assert event.error["message"] == error_data["message"]
        assert len(event.error["components"]) == 1
        assert event.error["components"][0]["name"] == "test-component"
        assert event.error["components"][0]["kind"] == "device"
        assert event.error["components"][0]["error"] == "Component error"
        assert event.data is None
        
        # Test serialization (output)
        output_serializer = Serializers.event(event, context={"object_id": event.object_id})
        output = output_serializer.data
        
        # When status="error", the error should be mirrored to data field
        assert output["error"]["message"] == error_data["message"]
        assert output["data"]["message"] == error_data["message"]
        assert output["status"] == "error"

    def test_error_in_data_field_new_behavior(self, account_objects):
        """Test that sending error info in the 'data' field works when status='error'"""
        error_data = {
            "message": "Test error message via data field",
            "components": [
                {
                    "name": "test-component-2",
                    "kind": "device",
                    "error": "Component error 2"
                }
            ]
        }
        
        data = {
            "object_id": "v0.1/test/config/device/test456",
            "status": "error",
            "data": error_data,  # Error info in data field instead of error field
            "org": account_objects.org.id,
            "user": account_objects.user.id
        }
        
        serializer = Serializers.event(data=data, context={"object_id": "v0.1/test/config/device/test456"})
        assert serializer.is_valid()
        
        # Save and retrieve
        event = serializer.save()
        
        # Verify data was transferred to error field internally
        assert event.status == "error"
        # Check essential fields (pydantic adds extra fields)
        assert event.error["message"] == error_data["message"]
        assert len(event.error["components"]) == 1
        assert event.error["components"][0]["name"] == "test-component-2"
        assert event.error["components"][0]["kind"] == "device"
        assert event.error["components"][0]["error"] == "Component error 2"
        assert event.data is None  # data field should be cleared after transfer
        
        # Test serialization (output)
        output_serializer = Serializers.event(event, context={"object_id": event.object_id})
        output = output_serializer.data
        
        # When status="error", the error should be mirrored to data field
        assert output["error"]["message"] == error_data["message"]
        assert output["data"]["message"] == error_data["message"]
        assert output["status"] == "error"

    def test_both_error_and_data_fields_set(self, account_objects):
        """Test that when both error and data fields are provided with status='error', error field takes precedence"""
        error_data = {
            "message": "Error field message",
            "components": []
        }
        
        # Use valid data for the normal schema (not error schema)
        other_data = {
            "components": [
                {
                    "name": "data-component",
                    "kind": "device",
                    "id": 999
                }
            ]
        }
        
        data = {
            "object_id": "v0.1/test/config/device/test789",
            "status": "error",
            "error": error_data,
            "data": other_data,
            "org": account_objects.org.id,
            "user": account_objects.user.id
        }
        
        serializer = Serializers.event(data=data, context={"object_id": "v0.1/test/config/device/test789"})
        assert serializer.is_valid()
        
        # Save and retrieve
        event = serializer.save()
        
        # Error field should take precedence
        assert event.status == "error"
        assert event.error["message"] == error_data["message"]
        # Data field is kept but validated with normal schema
        assert len(event.data["components"]) == 1
        assert event.data["components"][0]["name"] == "data-component"
        
        # Test serialization (output)
        output_serializer = Serializers.event(event, context={"object_id": event.object_id})
        output = output_serializer.data
        
        # When status="error", the error field is mirrored to data field in output
        assert output["error"]["message"] == error_data["message"]
        assert output["data"]["message"] == error_data["message"]  # data gets overwritten with error in output
        assert output["status"] == "error"

    def test_status_ok_with_data(self, account_objects):
        """Test normal behavior when status='ok' with data"""
        normal_data = {
            "components": [
                {
                    "name": "test-component",
                    "kind": "device",
                    "id": 123
                }
            ]
        }
        
        data = {
            "object_id": "v0.1/test/traffic/ix/1/test",
            "status": "ok",
            "data": normal_data,
            "org": account_objects.org.id,
            "user": account_objects.user.id
        }
        
        serializer = Serializers.event(data=data, context={"object_id": "v0.1/test/traffic/ix/1/test"})
        assert serializer.is_valid()
        
        # Save and retrieve
        event = serializer.save()
        
        # Verify normal behavior
        assert event.status == "ok"
        # Check essential fields are preserved
        assert len(event.data["components"]) == 1
        assert event.data["components"][0]["name"] == "test-component"
        assert event.data["components"][0]["kind"] == "device"
        assert event.data["components"][0]["id"] == 123
        assert event.error is None
        
        # Test serialization (output)
        output_serializer = Serializers.event(event, context={"object_id": event.object_id})
        output = output_serializer.data
        
        # When status="ok", data should not be mirrored to error
        assert len(output["data"]["components"]) == 1
        assert output["data"]["components"][0]["name"] == "test-component"
        assert output["error"] is None
        assert output["status"] == "ok"

    def test_blob_sanitization(self, account_objects):
        """Test that blob data is sanitized in the output"""
        error_data = {
            "message": "Error with blob",
            "components": [
                {
                    "name": "test-component",
                    "kind": "report",
                    "blob": "a" * 1000,  # Large blob data
                    "error": "Test error"
                }
            ]
        }
        
        event = Event.objects.create(
            object_id="v0.1/test/config/device/blob-test",
            status="error",
            error=error_data,
            org=account_objects.org,
            user=account_objects.user
        )
        
        # Test serialization
        serializer = Serializers.event(event, context={"object_id": event.object_id})
        output = serializer.data
        
        # Check blob sanitization
        component = output["error"]["components"][0]
        assert component["blob"] == "[Blob:1000 bytes]"
        
        # Also check in mirrored data field
        component = output["data"]["components"][0]
        assert component["blob"] == "[Blob:1000 bytes]"

    def test_list_serialization_with_different_schemas(self, account_objects):
        """Test that listing events with different object_ids uses correct schemas"""
        # Create events with different object_ids
        event1 = Event.objects.create(
            object_id="v0.1/test/config/device/test1",
            status="error",
            error={"message": "Device error", "components": []},
            org=account_objects.org
        )
        
        event2 = Event.objects.create(
            object_id="v0.1/test/traffic/ix/1/test",
            status="ok",
            data={"components": [{"kind": "ix", "id": 1, "name": "IX1"}]},
            org=account_objects.org
        )
        
        events = [event1, event2]
        
        # Serialize the list
        serializer = Serializers.event(events, many=True, context={"object_id": "v0.1/test"})
        output = serializer.data
        
        # Verify both events are serialized correctly
        assert len(output) == 2
        
        # First event (error)
        assert output[0]["status"] == "error"
        assert output[0]["error"]["message"] == "Device error"
        assert output[0]["data"]["message"] == "Device error"  # Mirrored
        
        # Second event (ok)
        assert output[1]["status"] == "ok"
        assert output[1]["data"]["components"][0]["kind"] == "ix"
        assert output[1]["error"] is None
        
    def test_error_data_validation_with_error_schema(self, account_objects):
        """Test that error data is validated with the correct error schema"""
        # Invalid error data (missing required 'message' field)
        invalid_error_data = {
            "components": [
                {
                    "name": "test-component",
                    "kind": "device",
                    "error": "Component error"
                }
            ]
            # Missing 'message' field which is required in ErrorDetails schema
        }
        
        data = {
            "object_id": "v0.1/test/config/device/test-invalid",
            "status": "error",
            "error": invalid_error_data,
            "org": account_objects.org.id,
            "user": account_objects.user.id
        }
        
        serializer = Serializers.event(data=data, context={"object_id": "v0.1/test/config/device/test-invalid"})
        assert not serializer.is_valid()
        assert "error" in serializer.errors 