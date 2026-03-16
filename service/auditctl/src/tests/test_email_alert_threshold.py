"""
Tests for the OrganizationEmailAlert threshold feature.

The threshold field controls how many consecutive error events must occur
for the same object_id before an email alert is sent. Duplicate alerts
within the same error streak are prevented via last_notified_at tracking.
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.utils import timezone
from django_auditctl.event_handlers import EmailAlert
from django_auditctl.models.auditctl import Event, OrganizationEmailAlert


def _create_event(org, object_id, status, minutes_ago=0):
    """Helper to create an Event with a specific timestamp."""
    created = timezone.now() - timedelta(minutes=minutes_ago)
    return Event.objects.create(
        object_id=object_id,
        status=status,
        org=org,
        error={"message": "test error"} if status == "error" else None,
        data={"components": []} if status == "ok" else None,
        created=created,
    )


OBJECT_ID = "v0.1/test/config/device-1"


@pytest.mark.django_db
class TestEmailAlertThreshold:
    """Tests for threshold-based email alerting."""

    def setup_method(self):
        """Common setup for each test."""
        from tests.fixtures import make_account_objects

        self.account = make_account_objects()
        self.org = self.account.org

    @patch("django_auditctl.event_handlers.send_plain")
    def test_threshold_1_ok_to_error_sends(self, mock_send):
        """threshold=1: ok->error sends email (backwards compatible)."""
        OrganizationEmailAlert.objects.create(
            org=self.org, email="alert@test.com", threshold=1
        )

        _create_event(self.org, OBJECT_ID, "ok", minutes_ago=2)
        error_event = _create_event(self.org, OBJECT_ID, "error", minutes_ago=1)

        handler = EmailAlert(error_event)
        handler()

        mock_send.assert_called_once()
        assert "alert@test.com" in mock_send.call_args[0][3]

    @patch("django_auditctl.event_handlers.send_plain")
    def test_threshold_1_error_to_error_does_not_resend(self, mock_send):
        """threshold=1: second error in same streak does NOT re-send."""
        alert = OrganizationEmailAlert.objects.create(
            org=self.org, email="alert@test.com", threshold=1
        )

        # First error triggers alert and sets last_notified_at
        first_error = _create_event(self.org, OBJECT_ID, "error", minutes_ago=2)
        handler = EmailAlert(first_error)
        handler()
        mock_send.assert_called_once()

        mock_send.reset_mock()

        # Second error should not resend (same streak, already notified)
        alert.refresh_from_db()
        second_error = _create_event(self.org, OBJECT_ID, "error", minutes_ago=1)
        handler = EmailAlert(second_error)
        handler()

        mock_send.assert_not_called()

    @patch("django_auditctl.event_handlers.send_plain")
    def test_threshold_1_first_event_is_error_sends(self, mock_send):
        """threshold=1: first-ever event is error, sends email."""
        OrganizationEmailAlert.objects.create(
            org=self.org, email="alert@test.com", threshold=1
        )

        error_event = _create_event(self.org, OBJECT_ID, "error", minutes_ago=1)

        handler = EmailAlert(error_event)
        handler()

        mock_send.assert_called_once()

    @patch("django_auditctl.event_handlers.send_plain")
    def test_threshold_1_sets_last_notified_at(self, mock_send):
        """Sending an alert updates last_notified_at on the alert."""
        alert = OrganizationEmailAlert.objects.create(
            org=self.org, email="alert@test.com", threshold=1
        )
        assert alert.last_notified_at is None

        error_event = _create_event(self.org, OBJECT_ID, "error", minutes_ago=1)
        handler = EmailAlert(error_event)
        handler()

        alert.refresh_from_db()
        assert alert.last_notified_at == error_event.created

    @patch("django_auditctl.event_handlers.send_plain")
    def test_threshold_3_first_error_no_send(self, mock_send):
        """threshold=3: 1st consecutive error does NOT send."""
        OrganizationEmailAlert.objects.create(
            org=self.org, email="alert@test.com", threshold=3
        )

        _create_event(self.org, OBJECT_ID, "ok", minutes_ago=4)
        error_event = _create_event(self.org, OBJECT_ID, "error", minutes_ago=3)

        handler = EmailAlert(error_event)
        handler()

        mock_send.assert_not_called()

    @patch("django_auditctl.event_handlers.send_plain")
    def test_threshold_3_second_error_no_send(self, mock_send):
        """threshold=3: 2nd consecutive error does NOT send."""
        OrganizationEmailAlert.objects.create(
            org=self.org, email="alert@test.com", threshold=3
        )

        _create_event(self.org, OBJECT_ID, "ok", minutes_ago=4)
        _create_event(self.org, OBJECT_ID, "error", minutes_ago=3)
        error_event = _create_event(self.org, OBJECT_ID, "error", minutes_ago=2)

        handler = EmailAlert(error_event)
        handler()

        mock_send.assert_not_called()

    @patch("django_auditctl.event_handlers.send_plain")
    def test_threshold_3_third_error_sends(self, mock_send):
        """threshold=3: 3rd consecutive error SENDS email."""
        OrganizationEmailAlert.objects.create(
            org=self.org, email="alert@test.com", threshold=3
        )

        _create_event(self.org, OBJECT_ID, "ok", minutes_ago=5)
        _create_event(self.org, OBJECT_ID, "error", minutes_ago=3)
        _create_event(self.org, OBJECT_ID, "error", minutes_ago=2)
        error_event = _create_event(self.org, OBJECT_ID, "error", minutes_ago=1)

        handler = EmailAlert(error_event)
        handler()

        mock_send.assert_called_once()

    @patch("django_auditctl.event_handlers.send_plain")
    def test_threshold_3_fourth_error_no_send(self, mock_send):
        """threshold=3: 4th consecutive error does NOT send (already alerted at 3)."""
        alert = OrganizationEmailAlert.objects.create(
            org=self.org, email="alert@test.com", threshold=3
        )

        _create_event(self.org, OBJECT_ID, "ok", minutes_ago=6)
        _create_event(self.org, OBJECT_ID, "error", minutes_ago=4)
        _create_event(self.org, OBJECT_ID, "error", minutes_ago=3)

        # 3rd error triggers and sets last_notified_at
        third_error = _create_event(self.org, OBJECT_ID, "error", minutes_ago=2)
        handler = EmailAlert(third_error)
        handler()
        mock_send.assert_called_once()

        mock_send.reset_mock()

        # 4th error should not re-send
        alert.refresh_from_db()
        fourth_error = _create_event(self.org, OBJECT_ID, "error", minutes_ago=1)
        handler = EmailAlert(fourth_error)
        handler()

        mock_send.assert_not_called()

    @patch("django_auditctl.event_handlers.send_plain")
    def test_threshold_3_missed_handler_still_sends(self, mock_send):
        """threshold=3: if the 3rd error handler was missed, 4th still sends."""
        OrganizationEmailAlert.objects.create(
            org=self.org, email="alert@test.com", threshold=3
        )

        # 3 errors but handler never ran (last_notified_at still None)
        _create_event(self.org, OBJECT_ID, "ok", minutes_ago=6)
        _create_event(self.org, OBJECT_ID, "error", minutes_ago=4)
        _create_event(self.org, OBJECT_ID, "error", minutes_ago=3)
        _create_event(self.org, OBJECT_ID, "error", minutes_ago=2)

        # 4th error: threshold is met and no prior notification, so it sends
        fourth_error = _create_event(self.org, OBJECT_ID, "error", minutes_ago=1)
        handler = EmailAlert(fourth_error)
        handler()

        mock_send.assert_called_once()

    @patch("django_auditctl.event_handlers.send_plain")
    def test_threshold_3_reset_after_ok(self, mock_send):
        """threshold=3: counter resets after ok, re-triggers on 3 new consecutive errors."""
        alert = OrganizationEmailAlert.objects.create(
            org=self.org, email="alert@test.com", threshold=3
        )

        # First batch of 3 errors - triggers alert
        _create_event(self.org, OBJECT_ID, "error", minutes_ago=10)
        _create_event(self.org, OBJECT_ID, "error", minutes_ago=9)
        third_error = _create_event(self.org, OBJECT_ID, "error", minutes_ago=8)
        handler = EmailAlert(third_error)
        handler()
        mock_send.assert_called_once()

        mock_send.reset_mock()

        # Reset with ok event
        _create_event(self.org, OBJECT_ID, "ok", minutes_ago=7)

        # Second batch of 3 errors - should re-trigger
        _create_event(self.org, OBJECT_ID, "error", minutes_ago=3)
        _create_event(self.org, OBJECT_ID, "error", minutes_ago=2)
        error_event = _create_event(self.org, OBJECT_ID, "error", minutes_ago=1)

        alert.refresh_from_db()
        handler = EmailAlert(error_event)
        handler()

        mock_send.assert_called_once()

    @patch("django_auditctl.event_handlers.send_plain")
    def test_mixed_thresholds_same_org(self, mock_send):
        """Different alerts with different thresholds fire independently."""
        OrganizationEmailAlert.objects.create(
            org=self.org, email="immediate@test.com", threshold=1
        )
        OrganizationEmailAlert.objects.create(
            org=self.org, email="delayed@test.com", threshold=3
        )

        # First error: only threshold=1 fires
        _create_event(self.org, OBJECT_ID, "ok", minutes_ago=5)
        error_event_1 = _create_event(self.org, OBJECT_ID, "error", minutes_ago=4)

        handler = EmailAlert(error_event_1)
        handler()

        assert mock_send.call_count == 1
        recipients = mock_send.call_args[0][3]
        assert "immediate@test.com" in recipients
        assert "delayed@test.com" not in recipients

        mock_send.reset_mock()

        # Third consecutive error: only threshold=3 fires
        _create_event(self.org, OBJECT_ID, "error", minutes_ago=2)
        error_event_3 = _create_event(self.org, OBJECT_ID, "error", minutes_ago=1)

        handler = EmailAlert(error_event_3)
        handler()

        assert mock_send.call_count == 1
        recipients = mock_send.call_args[0][3]
        assert "delayed@test.com" in recipients
        assert "immediate@test.com" not in recipients

    @patch("django_auditctl.event_handlers.send_plain")
    def test_disabled_alert_not_included(self, mock_send):
        """Disabled alerts are excluded even when threshold is met."""
        OrganizationEmailAlert.objects.create(
            org=self.org, email="disabled@test.com", threshold=1, enabled=False
        )

        _create_event(self.org, OBJECT_ID, "ok", minutes_ago=2)
        error_event = _create_event(self.org, OBJECT_ID, "error", minutes_ago=1)

        handler = EmailAlert(error_event)
        handler()

        mock_send.assert_not_called()

    @patch("django_auditctl.event_handlers.send_plain")
    def test_ok_event_does_not_trigger(self, mock_send):
        """An event with status=ok never triggers email alert."""
        OrganizationEmailAlert.objects.create(
            org=self.org, email="alert@test.com", threshold=1
        )

        ok_event = _create_event(self.org, OBJECT_ID, "ok", minutes_ago=1)

        handler = EmailAlert(ok_event)
        handler()

        mock_send.assert_not_called()

    @patch("django_auditctl.event_handlers.send_plain")
    def test_different_object_ids_independent(self, mock_send):
        """Consecutive errors are counted per object_id independently."""
        OrganizationEmailAlert.objects.create(
            org=self.org, email="alert@test.com", threshold=2
        )

        object_id_a = "v0.1/test/config/device-a"
        object_id_b = "v0.1/test/config/device-b"

        # 1 error on A, 1 error on B
        _create_event(self.org, object_id_a, "error", minutes_ago=3)
        _create_event(self.org, object_id_b, "error", minutes_ago=2)

        # 2nd error on A -> should send
        error_event_a = _create_event(self.org, object_id_a, "error", minutes_ago=1)

        handler = EmailAlert(error_event_a)
        handler()

        mock_send.assert_called_once()

    def test_qualifies_on_error(self):
        """EmailAlert.qualifies returns True for any error event."""
        error_event = _create_event(self.org, OBJECT_ID, "error", minutes_ago=1)
        handler = EmailAlert(error_event)
        assert handler.qualifies is True

    def test_qualifies_not_on_ok(self):
        """EmailAlert.qualifies returns False for ok events."""
        ok_event = _create_event(self.org, OBJECT_ID, "ok", minutes_ago=1)
        handler = EmailAlert(ok_event)
        assert handler.qualifies is False
