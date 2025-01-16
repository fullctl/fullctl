from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock

import pytest

from django_devicectl.models.tasks import (
    MemberTrafficAlertNotification,
    OperatorTrafficAlertNotification,
    TrafficThresholdAlerts,
)


class TrafficAlertNotificationBase:
    def setup(self):
        self.org = MagicMock(id=56, remote_id="remote-id", slug="test-slug")
        self.ix = MagicMock(id=21, traffic_poll_time=300, pdb_id=1)
        self.virtual_port = MagicMock(
            id=1,
            capacity_alert=0,
            capacity_notified_net=None,
            capacity_notified_ix=None,
            at_capacity=None,
        )

        self.auditctl_event = MagicMock(create=Mock())

        self.pdb_ix = MagicMock(
            tech_email="sample@test.com",
        )

        self.traffic_alert_email = MagicMock(
            subject="Sample email subject",
            message="Email message body",
        )
        self.ixctl_traffic_alert_email = MagicMock(
            get_traffic_alert_email=MagicMock(return_value=self.traffic_alert_email)
        )

        self.member = MagicMock(id=43, ref_id="ixctl:43", traffic_threshold_alert=34)


class TestOperatorTrafficAlertNotification(TrafficAlertNotificationBase):
    @pytest.fixture(autouse=True)
    def setup(self):
        super().setup()
        self.alert_email_type = "traffic_alert_ix"

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

        self.aaactl_poc.objects.assert_called_once()
        self.pdbctl_ix.object.call_count == 0
        self.ixctl_traffic_alert_email.get_traffic_alert_email.assert_called_once_with(
            ix_id=self.ix.id, email_type=self.alert_email_type, member_id=self.member.id
        )
        self.auditctl_event.create.assert_called_once()

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
            email_type=self.alert_email_type,
            member_id=self.member.id,
        )
        self.auditctl_event.create.assert_called_once()


class TestMemberTrafficAlertNotification(TrafficAlertNotificationBase):
    @pytest.fixture(autouse=True)
    def setup(self):
        super().setup()
        self.alert_email_type = "traffic_alert_net"

        self.poc = MagicMock(
            org=self.org.id,
            delivery_type="email",
            config=[
                {
                    "service": "peerctl",
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

        self.aaactl_poc.objects.assert_called_once()
        self.pdbctl_network_contact.objects.call_count == 0
        self.ixctl_traffic_alert_email.get_traffic_alert_email.assert_called_once_with(
            ix_id=self.ix.id, email_type=self.alert_email_type, member_id=self.member.id
        )
        self.auditctl_event.create.assert_called_once()
        assert self.ixctl_member.objects.call_count == 0

    def test_uses_pdb_recipients_if_no_poc(self):
        self.aaactl_poc.objects.return_value = []
        self.member_traffic_alert_notification.process_notification(
            virtual_port=self.virtual_port,
            member=self.member,
        )

        self.aaactl_poc.objects.assert_called_once()
        self.pdbctl_network_contact.objects.assert_called_once_with(
            asn=self.port_member.asn
        )
        self.ixctl_traffic_alert_email.get_traffic_alert_email.assert_called_once_with(
            ix_id=self.ix.id, email_type=self.alert_email_type, member_id=self.member.id
        )
        self.auditctl_event.create.assert_called_once()
        self.ixctl_member.objects.assert_called_once_with(ports=[self.virtual_port.id])


class TestTrafficThresholdAlert:
    @pytest.fixture(autouse=True)
    def setup(self):
        self.org = MagicMock(id=56, remote_id="remote-id", slug="test-slug")
        self.ix = MagicMock(id=21, traffic_poll_time=300, pdb_id=1)
        self.virtual_port = MagicMock(
            id=1,
            capacity_alert=0,
            capacity_notified_net=None,
            capacity_notified_ix=None,
            at_capacity=None,
        )

        self.members = [MagicMock(id=561, speed=30), MagicMock(id=243, speed=30)]

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

        self.traffic_threshold_alerts = TrafficThresholdAlerts(
            org=self.org,
            metrics=self.metrics,
            member_traffic_alert_notification=MagicMock(),
            operator_traffic_alert_notification=MagicMock(),
            ix=self.ix,
            members=self.members,
            traffic_alert_config=self.traffic_alert_config,
            peerctl_port_info=self.peerctl_port_info,
        )

    def test_when_traffic_greater_than_threshold_and_at_capacity(self):
        self.virtual_port = MagicMock(
            id=1,
            capacity_alert=24,
            capacity_notified_net=None,
            capacity_notified_ix=None,
            at_capacity=None,
        )
        self.traffic_threshold_alerts.process_traffic_threshold_alerts(
            virtual_port=self.virtual_port, traffic=90
        )

        self.metrics.write.assert_called_once()
        assert self.virtual_port.capacity_alert == 25
        assert self.virtual_port.capacity_notified_net
        assert self.virtual_port.capacity_notified_ix
        assert self.peerctl_port_info.objects.call_count == 2

    def test_when_traffic_greater_than_threshold_and_not_at_capacity(self):
        self.traffic_threshold_alerts.process_traffic_threshold_alerts(
            virtual_port=self.virtual_port, traffic=90
        )

        self.metrics.write.assert_called_once()
        assert self.virtual_port.capacity_alert == 1
        assert self.virtual_port.capacity_notified_net is None
        assert self.virtual_port.capacity_notified_ix is None
        assert self.peerctl_port_info.objects.call_count == 0

    def test_when_traffic_less_than_threshold_and_at_capacity(self):
        self.virtual_port = MagicMock(
            id=1,
            capacity_alert=24,
            capacity_notified_net=None,
            capacity_notified_ix=None,
            at_capacity=None,
        )
        self.traffic_threshold_alerts.process_traffic_threshold_alerts(
            virtual_port=self.virtual_port, traffic=10
        )

        self.metrics.write.assert_called_once()
        assert self.virtual_port.capacity_alert == 0
        assert self.virtual_port.capacity_notified_net is None
        assert self.virtual_port.capacity_notified_ix is None
        assert self.peerctl_port_info.objects.call_count == 0

    def test_when_traffic_less_than_threshold_and_not_at_capacity(self):
        self.virtual_port = MagicMock(
            id=1,
            capacity_alert=8,
            capacity_notified_net=None,
            capacity_notified_ix=None,
            at_capacity=None,
        )
        self.traffic_threshold_alerts.process_traffic_threshold_alerts(
            virtual_port=self.virtual_port, traffic=10
        )

        self.metrics.write.assert_called_once()
        assert self.virtual_port.capacity_alert == 0
        assert self.virtual_port.capacity_notified_net is None
        assert self.virtual_port.capacity_notified_ix is None
        assert self.peerctl_port_info.objects.call_count == 0

    def test_when_notification_is_sent_but_does_not_need_to_resend_yet(self):
        last_2_days = datetime.now() - timedelta(days=2)
        self.virtual_port = MagicMock(
            id=1,
            capacity_alert=24,
            capacity_notified_net=last_2_days,
            capacity_notified_ix=last_2_days,
            at_capacity=last_2_days,
        )
        self.traffic_threshold_alerts.process_traffic_threshold_alerts(
            virtual_port=self.virtual_port, traffic=90
        )

        self.metrics.write.assert_called_once()
        assert self.virtual_port.capacity_alert == 25
        assert self.virtual_port.capacity_notified_net == last_2_days
        assert self.virtual_port.capacity_notified_ix == last_2_days
        assert self.virtual_port.at_capacity > last_2_days
        assert self.peerctl_port_info.objects.call_count == 0

    def test_when_notification_sent_but_is_time_to_resend(self):
        last_8_days = datetime.now() - timedelta(days=8)
        self.virtual_port = MagicMock(
            id=1,
            capacity_alert=24,
            capacity_notified_net=last_8_days,
            capacity_notified_ix=last_8_days,
            at_capacity=last_8_days,
        )
        self.traffic_threshold_alerts.process_traffic_threshold_alerts(
            virtual_port=self.virtual_port, traffic=90
        )

        self.metrics.write.assert_called_once()
        assert self.virtual_port.capacity_alert == 25
        assert self.virtual_port.capacity_notified_net > last_8_days
        assert self.virtual_port.capacity_notified_ix > last_8_days
        assert self.virtual_port.at_capacity > last_8_days
        assert self.peerctl_port_info.objects.call_count == 2
