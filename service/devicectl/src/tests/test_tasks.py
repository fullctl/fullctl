from datetime import timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest
from django.utils import timezone
from django_devicectl.models.tasks import (
    MemberTrafficAlertNotification,
    OperatorTrafficAlertNotification,
    TrafficThresholdAlerts,
    default_graph_renderer,
)


class TrafficAlertNotificationBase:
    def setup(self):
        self.org = MagicMock(id=56, remote_id="remote-id", slug="test-slug")
        self.ix = MagicMock(id=21, traffic_poll_time=300, pdb_id=1)

        # Create a port for the virtual_port
        self.port = MagicMock(id=123)
        self.virtual_port = MagicMock(
            id=1,
            capacity_alert=0,
            capacity_notified_net=None,
            capacity_notified_ix=None,
            at_capacity=None,
            port=self.port,
        )

        self.auditctl_event = MagicMock(send_email=Mock())

        self.pdb_ix = MagicMock(
            tech_email="sample@test.com",
        )

        # Make traffic_alert_email an iterable (list) since the code iterates over it
        self.traffic_alert_email = [
            MagicMock(
                subject="Sample email subject",
                message="Email message body",
            )
        ]
        self.ixctl_traffic_alert_email = MagicMock(
            get_traffic_alert_email=MagicMock(return_value=self.traffic_alert_email)
        )

        self.member = MagicMock(
            id=43,
            ref_id="ixctl:43",
            traffic_threshold_alert=34,
            asn=542,
            port=self.port.id,
        )


class TestOperatorTrafficAlertNotification(TrafficAlertNotificationBase):
    @pytest.fixture(autouse=True)
    def setup(self):
        super().setup()
        self.poc = MagicMock(
            org=self.org.id,
            delivery_type="email",
            config=[
                {
                    "service": "ixctl",
                    "recipients": ["test@test.com", "example@example.com"],
                }
            ],
            type="notifications",
            status="ok",
        )

        def aaactl_poc_mock():
            yield from [self.poc]

        self.aaactl_poc = MagicMock(objects=MagicMock(return_value=aaactl_poc_mock()))

        self.pdbctl_ix = MagicMock(object=Mock(return_value=self.pdb_ix))
        self.operator_traffic_alert_notification = OperatorTrafficAlertNotification(
            org=self.org,
            ixctl_traffic_alert_email=self.ixctl_traffic_alert_email,
            auditctl_event=self.auditctl_event,
            aaactl_poc=self.aaactl_poc,
            pdbctl_ix=self.pdbctl_ix,
            ix=self.ix,
        )

    def test_uses_poc_recipients(self):
        self.operator_traffic_alert_notification.process_notification(
            virtual_port=self.virtual_port,
            member=self.member,
        )

        self.aaactl_poc.objects.assert_called_once_with(
            org=self.org.slug,
            type="notifications",
            delivery_type="email",
            status="ok",
            service=self.operator_traffic_alert_notification.alert_service_type,
        )
        self.pdbctl_ix.object.call_count == 0
        self.ixctl_traffic_alert_email.get_traffic_alert_email.assert_called_once_with(
            ix_id=self.ix.id,
            email_type=self.operator_traffic_alert_notification.alert_email_type,
            member_id=self.member.id,
        )
        self.auditctl_event.send_email.assert_called_once()

    def test_uses_pdb_recipients_if_no_poc(self):
        self.aaactl_poc.objects.return_value = []
        self.operator_traffic_alert_notification.process_notification(
            virtual_port=self.virtual_port,
            member=self.member,
        )

        self.aaactl_poc.objects.assert_called_once()
        self.pdbctl_ix.object.assert_called_once_with(id=self.ix.pdb_id)
        self.ixctl_traffic_alert_email.get_traffic_alert_email.assert_called_once_with(
            ix_id=self.ix.id,
            email_type=self.operator_traffic_alert_notification.alert_email_type,
            member_id=self.member.id,
        )
        self.auditctl_event.send_email.assert_called_once()


class TestMemberTrafficAlertNotification(TrafficAlertNotificationBase):
    @pytest.fixture(autouse=True)
    def setup(self):
        super().setup()
        self.poc = MagicMock(
            org=self.org.id,
            delivery_type="email",
            config=[
                {
                    "service": "peerctl",
                    "entity": self.member.asn,
                    "recipients": ["test@test.com", "example@example.com"],
                }
            ],
            type="notifications",
            status="ok",
        )

        def aaactl_poc_mock():
            yield from [self.poc]

        self.aaactl_poc = MagicMock(objects=MagicMock(return_value=aaactl_poc_mock()))

        self.port_member = MagicMock(asn=30)

        def ixctl_port_member_mock():
            yield from [self.port_member]

        self.ixctl_member = MagicMock(
            objects=MagicMock(return_value=ixctl_port_member_mock())
        )

        self.network_contact = MagicMock(role="Technical", email="test@test.com")

        def pdbctl_network_contact_mock():
            yield from [self.network_contact]

        self.pdbctl_network_contact = MagicMock(
            objects=MagicMock(return_value=pdbctl_network_contact_mock())
        )

        self.member_traffic_alert_notification = MemberTrafficAlertNotification(
            org=self.org,
            ixctl_traffic_alert_email=self.ixctl_traffic_alert_email,
            ixctl_member=self.ixctl_member,
            auditctl_event=self.auditctl_event,
            aaactl_poc=self.aaactl_poc,
            ix=self.ix,
            pdbctl_network_contact=self.pdbctl_network_contact,
        )

    def test_uses_poc_recipients(self):
        self.member_traffic_alert_notification.process_notification(
            virtual_port=self.virtual_port,
            member=self.member,
        )

        self.aaactl_poc.objects.assert_called_once_with(
            type="notifications",
            delivery_type="email",
            status="ok",
            service=self.member_traffic_alert_notification.alert_service_type,
            entity=self.member.asn,
        )
        self.pdbctl_network_contact.objects.call_count == 0
        self.ixctl_traffic_alert_email.get_traffic_alert_email.assert_called_once_with(
            ix_id=self.ix.id,
            email_type=self.member_traffic_alert_notification.alert_email_type,
            member_id=self.member.id,
        )
        self.auditctl_event.send_email.assert_called_once()
        assert self.ixctl_member.objects.call_count == 0

    def test_uses_pdb_recipients_if_no_poc(self):
        self.aaactl_poc.objects.return_value = []
        self.member_traffic_alert_notification.process_notification(
            virtual_port=self.virtual_port,
            member=self.member,
        )

        self.aaactl_poc.objects.assert_called_once()
        # Fix the query parameter to use the member's asn
        self.pdbctl_network_contact.objects.assert_called_once_with(asn=self.member.asn)
        self.ixctl_traffic_alert_email.get_traffic_alert_email.assert_called_once_with(
            ix_id=self.ix.id,
            email_type=self.member_traffic_alert_notification.alert_email_type,
            member_id=self.member.id,
        )
        self.auditctl_event.send_email.assert_called_once()


class TestTrafficThresholdAlert:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.org = MagicMock(id=56, remote_id="remote-id", slug="test-slug")
        self.ix = MagicMock(id=21, traffic_poll_time=300, pdb_id=1)

        # Create a port for the virtual_port
        self.port = MagicMock(id=123)
        self.virtual_port = MagicMock(
            id=1,
            capacity_alert=0,
            capacity_notified_net=None,
            capacity_notified_ix=None,
            at_capacity=None,
            port=self.port,
        )

        # Create member with port ID that matches the virtual_port
        self.member = MagicMock(id=561, speed=30, port=self.port.id)
        self.members = [self.member, MagicMock(id=243, speed=30)]

        self.traffic_alert_config = MagicMock(
            ix=self.ix.id,
            traffic_level=90,
            time_period=120,
            operator_emails=True,
            member_emails=True,
            operator_emails_max_frequency=7,
            member_emails_max_frequency=7,
        )

        self.metrics = MagicMock(write=Mock())

        def peerctl_port_info_mock():
            yield from [
                MagicMock(ref_id=f"ixctl:{member.id}", traffic_threshold_alert=True)
                for member in self.members
            ]

        self.peerctl_port_info = MagicMock(
            objects=MagicMock(return_value=peerctl_port_info_mock())
        )

        # Create notification mocks
        # Create notification mocks with detailed implementation to handle calls properly
        self.member_notification = MagicMock(
            process_notification=Mock(),
            get_recipients=Mock(return_value=["test@example.com"]),
            get_traffic_alert_email=Mock(return_value=True),
            send_notification=Mock(),
        )
        self.operator_notification = MagicMock(
            process_notification=Mock(),
            get_recipients=Mock(return_value=["test@example.com"]),
            get_traffic_alert_email=Mock(return_value=True),
            send_notification=Mock(),
        )

        self.traffic_threshold_alerts = TrafficThresholdAlerts(
            org=self.org,
            metrics=self.metrics,
            member_traffic_alert_notification=self.member_notification,
            operator_traffic_alert_notification=self.operator_notification,
            ix=self.ix,
            members=self.members,
            traffic_alert_config=self.traffic_alert_config,
            peerctl_port_info=self.peerctl_port_info,
        )

        # Create members_by_port mapping
        self.traffic_threshold_alerts.members_by_port = {
            self.virtual_port.port.id: self.member
        }

    def test_when_traffic_greater_than_threshold_and_at_capacity(self):
        # Set capacity alert high enough to trigger notification
        self.virtual_port = MagicMock(
            id=1,
            port=self.port,
            capacity_alert=24,
            capacity_notified_net=None,
            capacity_notified_ix=None,
            at_capacity=None,
            save=Mock(),
        )

        # Update members_by_port with new virtual_port's port
        self.traffic_threshold_alerts.members_by_port = {self.port.id: self.member}

        # Traffic threshold = speed * 1_000_000 * traffic_level / 100
        # For 30Mbps port with 90% threshold = 27,000,000 bps
        # Use traffic value above threshold
        self.traffic_threshold_alerts.process_traffic_threshold_alerts(
            virtual_port=self.virtual_port, traffic=28_000_000
        )

        self.metrics.write.assert_called_once()
        assert self.virtual_port.capacity_alert == 25
        assert self.virtual_port.at_capacity is not None
        assert self.virtual_port.save.call_count >= 1

        # Check both notifications were processed
        self.operator_notification.process_notification.assert_called_once()
        self.member_notification.process_notification.assert_called_once()

    def test_when_traffic_greater_than_threshold_and_not_at_capacity(self):
        self.virtual_port = MagicMock(
            id=1,
            port=self.port,
            capacity_alert=0,  # Not enough alerts to trigger notification
            capacity_notified_net=None,
            capacity_notified_ix=None,
            at_capacity=None,
            save=Mock(),
        )

        self.traffic_threshold_alerts.members_by_port = {self.port.id: self.member}

        # Use traffic value above threshold
        self.traffic_threshold_alerts.process_traffic_threshold_alerts(
            virtual_port=self.virtual_port, traffic=28_000_000
        )

        self.metrics.write.assert_called_once()
        assert self.virtual_port.capacity_alert == 1
        assert self.virtual_port.at_capacity is None
        assert self.virtual_port.save.call_count >= 1

        # No notifications should be sent
        self.operator_notification.process_notification.assert_not_called()
        self.member_notification.process_notification.assert_not_called()

    def test_when_traffic_less_than_threshold_and_at_capacity(self):
        self.virtual_port = MagicMock(
            id=1,
            port=self.port,
            capacity_alert=24,  # High alert count
            capacity_notified_net=None,
            capacity_notified_ix=None,
            at_capacity=None,
            save=Mock(),
        )

        self.traffic_threshold_alerts.members_by_port = {self.port.id: self.member}

        # Use traffic value below threshold
        self.traffic_threshold_alerts.process_traffic_threshold_alerts(
            virtual_port=self.virtual_port, traffic=20_000_000
        )

        self.metrics.write.assert_called_once()
        assert self.virtual_port.capacity_alert == 0  # Reset to zero
        assert self.virtual_port.at_capacity is None
        assert self.virtual_port.save.call_count >= 1

        # No notifications should be sent
        self.operator_notification.process_notification.assert_not_called()
        self.member_notification.process_notification.assert_not_called()

    def test_when_traffic_less_than_threshold_and_not_at_capacity(self):
        self.virtual_port = MagicMock(
            id=1,
            port=self.port,
            capacity_alert=8,  # Some alerts but not enough to trigger
            capacity_notified_net=None,
            capacity_notified_ix=None,
            at_capacity=None,
            save=Mock(),
        )

        self.traffic_threshold_alerts.members_by_port = {self.port.id: self.member}

        # Use traffic value below threshold
        self.traffic_threshold_alerts.process_traffic_threshold_alerts(
            virtual_port=self.virtual_port, traffic=20_000_000
        )

        self.metrics.write.assert_called_once()
        assert self.virtual_port.capacity_alert == 0  # Reset to zero
        assert self.virtual_port.at_capacity is None
        assert self.virtual_port.save.call_count >= 1

        # No notifications should be sent
        self.operator_notification.process_notification.assert_not_called()
        self.member_notification.process_notification.assert_not_called()

    def test_when_notification_is_sent_but_does_not_need_to_resend_yet(self):
        # Use timezone.now() to create timezone-aware datetimes
        last_2_days = timezone.now() - timedelta(days=2)
        self.virtual_port = MagicMock(
            id=1,
            port=self.port,
            capacity_alert=24,
            capacity_notified_net=last_2_days,
            capacity_notified_ix=last_2_days,
            at_capacity=last_2_days,
            save=Mock(),
        )

        self.traffic_threshold_alerts.members_by_port = {self.port.id: self.member}

        # Use traffic value above threshold
        self.traffic_threshold_alerts.process_traffic_threshold_alerts(
            virtual_port=self.virtual_port, traffic=28_000_000
        )

        self.metrics.write.assert_called_once()
        assert self.virtual_port.capacity_alert == 25
        assert self.virtual_port.at_capacity is not None
        assert self.virtual_port.at_capacity > last_2_days
        assert self.virtual_port.save.call_count >= 1

        # No notifications should be sent because last notification was too recent
        self.operator_notification.process_notification.assert_not_called()
        self.member_notification.process_notification.assert_not_called()

    def test_when_notification_sent_but_is_time_to_resend(self):
        # Use timezone.now() to create timezone-aware datetimes
        last_8_days = timezone.now() - timedelta(days=8)
        self.virtual_port = MagicMock(
            id=1,
            port=self.port,
            capacity_alert=24,
            capacity_notified_net=last_8_days,
            capacity_notified_ix=last_8_days,
            at_capacity=last_8_days,
            save=Mock(),
        )

        self.traffic_threshold_alerts.members_by_port = {self.port.id: self.member}

        # Use traffic value above threshold
        self.traffic_threshold_alerts.process_traffic_threshold_alerts(
            virtual_port=self.virtual_port, traffic=28_000_000
        )

        self.metrics.write.assert_called_once()
        assert self.virtual_port.capacity_alert == 25
        assert self.virtual_port.at_capacity is not None
        assert self.virtual_port.at_capacity > last_8_days
        assert self.virtual_port.save.call_count >= 1

        # Notifications should be sent because enough time has passed
        self.operator_notification.process_notification.assert_called_once()
        self.member_notification.process_notification.assert_called_once()

    def test_skips_member_notification_when_threshold_alerts_not_activated(self):
        # Create a custom port_info mock that returns traffic_threshold_alert=False
        def peerctl_port_info_mock_disabled():
            yield from [
                MagicMock(
                    ref_id=f"ixctl:{self.member.id}", traffic_threshold_alert=False
                )
            ]

        self.peerctl_port_info.objects.return_value = peerctl_port_info_mock_disabled()

        self.virtual_port = MagicMock(
            id=1,
            port=self.port,
            capacity_alert=24,
            capacity_notified_net=None,
            capacity_notified_ix=None,
            at_capacity=None,
            save=Mock(),
        )

        self.traffic_threshold_alerts.members_by_port = {self.port.id: self.member}

        # Use traffic value above threshold
        self.traffic_threshold_alerts.process_traffic_threshold_alerts(
            virtual_port=self.virtual_port, traffic=28_000_000
        )

        # Only operator notification should be sent, not member notification
        self.operator_notification.process_notification.assert_called_once()
        self.member_notification.process_notification.assert_not_called()


@pytest.mark.parametrize(
    "rrd_enabled, ts_db_url, expected",
    [
        (True, None, "rrd"),
        (False, None, None),
        (False, "https://example.com", "victoriametrics"),
        (True, "https://example.com", "rrd"),
    ],
)
def test_default_graph_renderer(
    settings, rrd_enabled: bool, ts_db_url: str | None, expected: str
):
    settings.GRAPHS_RRD_ENABLED = rrd_enabled
    settings.TIMESERIES_DB_URL = ts_db_url

    assert default_graph_renderer() == expected
