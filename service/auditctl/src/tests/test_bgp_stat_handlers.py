"""
Tests for BGPSessionStateDataHandler and BatchedBGPSessionStateDataHandler.

These handlers receive BGP stat events from route servers and write stats to
physical ports via devicectl. The key invariant: member lookup must be scoped
to the RS's own IX to prevent cross-IX stat leakage.
"""

from unittest.mock import MagicMock, patch

import pytest
from django_auditctl.event_handlers import (
    BatchedBGPSessionStateDataHandler,
    BGPSessionStateDataHandler,
)


def _make_event(object_id, components):
    event = MagicMock()
    event.object_id = object_id
    event.data = {"components": components}
    return event


def _make_rs(ix_id=10):
    rs = MagicMock()
    rs.ix_id = ix_id
    return rs


def _make_member(port=101, ipaddr4="192.0.2.1", ipaddr6=None, asn=64500):
    member = MagicMock()
    member.port = port
    member.ipaddr4 = ipaddr4
    member.ipaddr6 = ipaddr6
    member.asn = asn
    return member


def _make_port(port_id=101, physical_port_ids=(1001,)):
    port = MagicMock()
    port.id = port_id
    port.physical_ports = [{"id": pid} for pid in physical_port_ids]
    return port


COMPONENT = {
    "asn": "64500",
    "address": "192.0.2.1",
    "routeserver_router_id": "10.0.0.1",
    "routeserver_hostname": "rs1.example.com",
}


@pytest.mark.django_db
class TestBGPSessionStateDataHandler:
    def _make_handler(self, components):
        event = _make_event("v0.1/test-org/bgp/stat/10.0.0.1/179", components)
        handler = BGPSessionStateDataHandler(event)
        handler.heartbeat = MagicMock()
        return handler

    def test_empty_components_returns_early(self):
        handler = self._make_handler([])

        with patch("fullctl.service_bridge.ixctl.Routeserver") as mock_rs_cls:
            handler()
            mock_rs_cls.assert_not_called()

    def test_rs_not_found_returns_early(self):
        handler = self._make_handler([COMPONENT])

        with (
            patch("django_auditctl.event_handlers.ixctl.Routeserver") as mock_rs_cls,
            patch(
                "django_auditctl.event_handlers.ixctl.InternetExchangeMember"
            ) as mock_member_cls,
        ):
            mock_rs_cls.return_value.first.return_value = None

            handler()

            mock_rs_cls.return_value.first.assert_called_once_with(ip="10.0.0.1")
            # Class is instantiated before the RS check, but .objects() must not be called
            mock_member_cls.return_value.objects.assert_not_called()

    def test_member_lookup_filtered_by_ix(self):
        handler = self._make_handler([COMPONENT])
        rs = _make_rs(ix_id=42)
        member = _make_member(port=101, ipaddr4="192.0.2.1")
        port = _make_port(port_id=101, physical_port_ids=(1001,))

        with (
            patch("django_auditctl.event_handlers.ixctl.Routeserver") as mock_rs_cls,
            patch(
                "django_auditctl.event_handlers.ixctl.InternetExchangeMember"
            ) as mock_member_cls,
            patch("django_auditctl.event_handlers.devicectl.Port") as mock_port_cls,
            patch(
                "django_auditctl.event_handlers.devicectl.PhysicalPortStats"
            ) as mock_stats_cls,
        ):
            mock_rs_cls.return_value.first.return_value = rs
            mock_member_cls.return_value.objects.return_value = [member]
            mock_port_cls.return_value.objects.return_value = [port]

            handler()

            # Verify ix filter was applied to the member lookup
            call_kwargs = mock_member_cls.return_value.objects.call_args[1]
            assert call_kwargs["ix"] == 42
            assert call_kwargs["asn"] == 64500
            assert call_kwargs["ipaddr4"] == "192.0.2.1"
            assert call_kwargs["is_rs_peer"] is True

    def test_stats_saved_to_correct_physical_port(self):
        handler = self._make_handler([COMPONENT])
        rs = _make_rs(ix_id=42)
        member = _make_member(port=101, ipaddr4="192.0.2.1")
        port = _make_port(port_id=101, physical_port_ids=(1001,))

        with (
            patch("django_auditctl.event_handlers.ixctl.Routeserver") as mock_rs_cls,
            patch(
                "django_auditctl.event_handlers.ixctl.InternetExchangeMember"
            ) as mock_member_cls,
            patch("django_auditctl.event_handlers.devicectl.Port") as mock_port_cls,
            patch(
                "django_auditctl.event_handlers.devicectl.PhysicalPortStats"
            ) as mock_stats_cls,
        ):
            mock_rs_cls.return_value.first.return_value = rs
            mock_member_cls.return_value.objects.return_value = [member]
            mock_port_cls.return_value.objects.return_value = [port]

            handler()

            mock_stats_cls.return_value.save_physical_port_stats.assert_called_once_with(
                data=[COMPONENT],
                org_slug="test-org",
                physical_port=1001,
                stat_type="bgp_stats",
            )

    def test_no_port_assigned_skips_stats(self):
        handler = self._make_handler([COMPONENT])
        rs = _make_rs(ix_id=42)
        # no port
        member = _make_member(port=None, ipaddr4="192.0.2.1")

        with (
            patch("django_auditctl.event_handlers.ixctl.Routeserver") as mock_rs_cls,
            patch(
                "django_auditctl.event_handlers.ixctl.InternetExchangeMember"
            ) as mock_member_cls,
            patch(
                "django_auditctl.event_handlers.devicectl.PhysicalPortStats"
            ) as mock_stats_cls,
        ):
            mock_rs_cls.return_value.first.return_value = rs
            mock_member_cls.return_value.objects.return_value = [member]

            handler()

            mock_stats_cls.return_value.save_physical_port_stats.assert_not_called()

    def test_missing_routeserver_router_id_returns_early(self):
        """Component with no routeserver_router_id -> RS lookup returns None -> early return."""
        component = {**COMPONENT, "routeserver_router_id": None}
        handler = self._make_handler([component])

        with (
            patch("django_auditctl.event_handlers.ixctl.Routeserver") as mock_rs_cls,
            patch(
                "django_auditctl.event_handlers.ixctl.InternetExchangeMember"
            ) as mock_member_cls,
        ):
            mock_rs_cls.return_value.first.return_value = None

            handler()

            mock_rs_cls.return_value.first.assert_called_once_with(ip=None)
            mock_member_cls.return_value.objects.assert_not_called()

    def test_ipv6_member_lookup(self):
        """Component with IPv6 address uses ipaddr6 filter instead of ipaddr4."""
        component = {
            "asn": "64500",
            "address": "2001:db8::1",
            "routeserver_router_id": "10.0.0.1",
            "routeserver_hostname": "rs1.example.com",
        }
        handler = self._make_handler([component])
        rs = _make_rs(ix_id=42)
        member = _make_member(port=101, ipaddr4=None, ipaddr6="2001:db8::1")
        port = _make_port(port_id=101, physical_port_ids=(1001,))

        with (
            patch("django_auditctl.event_handlers.ixctl.Routeserver") as mock_rs_cls,
            patch(
                "django_auditctl.event_handlers.ixctl.InternetExchangeMember"
            ) as mock_member_cls,
            patch("django_auditctl.event_handlers.devicectl.Port") as mock_port_cls,
            patch("django_auditctl.event_handlers.devicectl.PhysicalPortStats"),
        ):
            mock_rs_cls.return_value.first.return_value = rs
            mock_member_cls.return_value.objects.return_value = [member]
            mock_port_cls.return_value.objects.return_value = [port]

            handler()

            call_kwargs = mock_member_cls.return_value.objects.call_args[1]
            assert "ipaddr6" in call_kwargs
            assert call_kwargs["ipaddr6"] == "2001:db8::1"
            assert "ipaddr4" not in call_kwargs

    def test_no_members_found_skips_stats(self):
        """No members match the IX-scoped lookup -> port_ids is empty -> early return."""
        handler = self._make_handler([COMPONENT])
        rs = _make_rs(ix_id=42)

        with (
            patch("django_auditctl.event_handlers.ixctl.Routeserver") as mock_rs_cls,
            patch(
                "django_auditctl.event_handlers.ixctl.InternetExchangeMember"
            ) as mock_member_cls,
            patch(
                "django_auditctl.event_handlers.devicectl.PhysicalPortStats"
            ) as mock_stats_cls,
        ):
            mock_rs_cls.return_value.first.return_value = rs
            mock_member_cls.return_value.objects.return_value = []

            handler()

            mock_stats_cls.return_value.save_physical_port_stats.assert_not_called()


@pytest.mark.django_db
class TestBatchedBGPSessionStateDataHandler:
    def _make_handler(self, components):
        event = _make_event("v0.2/test-org/bgp/stat/10.0.0.1", components)
        handler = BatchedBGPSessionStateDataHandler(event)
        handler.heartbeat = MagicMock()
        return handler

    def test_empty_components_returns_early(self):
        handler = self._make_handler([])

        with patch("django_auditctl.event_handlers.ixctl.Routeserver") as mock_rs_cls:
            handler()
            mock_rs_cls.assert_not_called()

    def test_rs_not_found_returns_early(self):
        handler = self._make_handler([COMPONENT])

        with (
            patch("django_auditctl.event_handlers.ixctl.Routeserver") as mock_rs_cls,
            patch(
                "django_auditctl.event_handlers.ixctl.InternetExchangeMember"
            ) as mock_member_cls,
        ):
            mock_rs_cls.return_value.first.return_value = None

            handler()

            mock_rs_cls.return_value.first.assert_called_once_with(ip="10.0.0.1")
            # Class is instantiated before the RS check, but .first() must not be called
            mock_member_cls.return_value.first.assert_not_called()

    def test_member_lookup_filtered_by_ix(self):
        handler = self._make_handler([COMPONENT])
        rs = _make_rs(ix_id=99)
        member = _make_member(port=201, ipaddr4="192.0.2.1")
        port = _make_port(port_id=201, physical_port_ids=(2001,))

        with (
            patch("django_auditctl.event_handlers.ixctl.Routeserver") as mock_rs_cls,
            patch(
                "django_auditctl.event_handlers.ixctl.InternetExchangeMember"
            ) as mock_member_cls,
            patch("django_auditctl.event_handlers.devicectl.Port") as mock_port_cls,
            patch(
                "django_auditctl.event_handlers.devicectl.PhysicalPortStats"
            ) as mock_stats_cls,
        ):
            mock_rs_cls.return_value.first.return_value = rs
            mock_member_cls.return_value.first.return_value = member
            mock_port_cls.return_value.objects.return_value = [port]

            handler()

            call_kwargs = mock_member_cls.return_value.first.call_args[1]
            assert call_kwargs["ix"] == 99
            assert call_kwargs["asn"] == 64500
            assert call_kwargs["ipaddr4"] == "192.0.2.1"
            assert call_kwargs["is_rs_peer"] is True

    def test_stats_saved_to_correct_physical_port(self):
        handler = self._make_handler([COMPONENT])
        rs = _make_rs(ix_id=99)
        member = _make_member(port=201, ipaddr4="192.0.2.1")
        port = _make_port(port_id=201, physical_port_ids=(2001,))

        with (
            patch("django_auditctl.event_handlers.ixctl.Routeserver") as mock_rs_cls,
            patch(
                "django_auditctl.event_handlers.ixctl.InternetExchangeMember"
            ) as mock_member_cls,
            patch("django_auditctl.event_handlers.devicectl.Port") as mock_port_cls,
            patch(
                "django_auditctl.event_handlers.devicectl.PhysicalPortStats"
            ) as mock_stats_cls,
        ):
            mock_rs_cls.return_value.first.return_value = rs
            mock_member_cls.return_value.first.return_value = member
            mock_port_cls.return_value.objects.return_value = [port]

            handler()

            mock_stats_cls.return_value.save_physical_port_stats.assert_called_once_with(
                data=[COMPONENT],
                org_slug="test-org",
                physical_port=2001,
                stat_type="bgp_stats",
            )

    def test_member_cached_per_asn_address_key(self):
        """Same (asn, address) key should only trigger one member lookup."""
        # same asn + address
        component_dup = dict(COMPONENT)
        handler = self._make_handler([COMPONENT, component_dup])
        rs = _make_rs(ix_id=99)
        # Return a real member so the key gets stored in the cache dict
        # no port, so stat saving is skipped
        member = _make_member(port=None)

        with (
            patch("django_auditctl.event_handlers.ixctl.Routeserver") as mock_rs_cls,
            patch(
                "django_auditctl.event_handlers.ixctl.InternetExchangeMember"
            ) as mock_member_cls,
            patch("django_auditctl.event_handlers.devicectl.PhysicalPortStats"),
        ):
            mock_rs_cls.return_value.first.return_value = rs
            mock_member_cls.return_value.first.return_value = member

            handler()

            # Only one lookup despite two identical components
            assert mock_member_cls.return_value.first.call_count == 1

    def test_no_port_assigned_skips_stats(self):
        handler = self._make_handler([COMPONENT])
        rs = _make_rs(ix_id=99)
        member = _make_member(port=None, ipaddr4="192.0.2.1")

        with (
            patch("django_auditctl.event_handlers.ixctl.Routeserver") as mock_rs_cls,
            patch(
                "django_auditctl.event_handlers.ixctl.InternetExchangeMember"
            ) as mock_member_cls,
            patch(
                "django_auditctl.event_handlers.devicectl.PhysicalPortStats"
            ) as mock_stats_cls,
        ):
            mock_rs_cls.return_value.first.return_value = rs
            mock_member_cls.return_value.first.return_value = member

            handler()

            mock_stats_cls.return_value.save_physical_port_stats.assert_not_called()

    def test_missing_routeserver_router_id_returns_early(self):
        """Component with no routeserver_router_id -> RS lookup returns None -> early return."""
        component = {**COMPONENT, "routeserver_router_id": None}
        handler = self._make_handler([component])

        with (
            patch("django_auditctl.event_handlers.ixctl.Routeserver") as mock_rs_cls,
            patch(
                "django_auditctl.event_handlers.ixctl.InternetExchangeMember"
            ) as mock_member_cls,
        ):
            mock_rs_cls.return_value.first.return_value = None

            handler()

            mock_rs_cls.return_value.first.assert_called_once_with(ip=None)
            mock_member_cls.return_value.first.assert_not_called()

    def test_ipv6_member_lookup(self):
        """Component with IPv6 address uses ipaddr6 filter instead of ipaddr4."""
        component = {
            "asn": "64500",
            "address": "2001:db8::1",
            "routeserver_router_id": "10.0.0.1",
            "routeserver_hostname": "rs1.example.com",
        }
        handler = self._make_handler([component])
        rs = _make_rs(ix_id=99)
        member = _make_member(port=None, ipaddr4=None, ipaddr6="2001:db8::1")

        with (
            patch("django_auditctl.event_handlers.ixctl.Routeserver") as mock_rs_cls,
            patch(
                "django_auditctl.event_handlers.ixctl.InternetExchangeMember"
            ) as mock_member_cls,
        ):
            mock_rs_cls.return_value.first.return_value = rs
            mock_member_cls.return_value.first.return_value = member

            handler()

            call_kwargs = mock_member_cls.return_value.first.call_args[1]
            assert "ipaddr6" in call_kwargs
            assert call_kwargs["ipaddr6"] == "2001:db8::1"
            assert "ipaddr4" not in call_kwargs

    def test_no_members_found_skips_stats(self):
        """No members match the IX-scoped lookup -> port_ids is empty -> early return."""
        handler = self._make_handler([COMPONENT])
        rs = _make_rs(ix_id=99)

        with (
            patch("django_auditctl.event_handlers.ixctl.Routeserver") as mock_rs_cls,
            patch(
                "django_auditctl.event_handlers.ixctl.InternetExchangeMember"
            ) as mock_member_cls,
            patch(
                "django_auditctl.event_handlers.devicectl.PhysicalPortStats"
            ) as mock_stats_cls,
        ):
            mock_rs_cls.return_value.first.return_value = rs
            mock_member_cls.return_value.first.return_value = None

            handler()

            mock_stats_cls.return_value.save_physical_port_stats.assert_not_called()
