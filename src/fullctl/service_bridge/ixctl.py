try:
    from django.conf import settings

    DEFAULT_SERVICE_KEY = settings.SERVICE_KEY
except ImportError:
    DEFAULT_SERVICE_KEY = ""

import ipaddress

import fullctl.service_bridge.pdbctl as pdbctl
from fullctl.service_bridge.client import Bridge, DataObject, url_join

CACHE = {}


class IxctlEntity(DataObject):
    source = "ixctl"
    description = "Ixctl Object"


class Ixctl(Bridge):

    """
    Service bridge for ixctl data retrieval
    """

    class Meta:
        service = "ixctl"
        ref_tag = "base"
        data_object_cls = IxctlEntity

    def __init__(self, key=None, org=None, **kwargs):
        if not key:
            key = DEFAULT_SERVICE_KEY

        kwargs.setdefault("cache_duration", 10)
        kwargs.setdefault("cache", CACHE)

        super().__init__(settings.IXCTL_URL, key, org, **kwargs)
        self.url = url_join(self.url, "service-bridge/")


class InternetExchangeObject(IxctlEntity):
    description = "Ixctl Exchange"


class InternetExchange(Ixctl):
    class Meta(Ixctl.Meta):
        ref_tag = "ix"
        data_object_cls = InternetExchangeObject


class InternetExhangePrefixObject(IxctlEntity):
    description = "Ixctl Exchange Prefix"
    relationships = {
        "ix": {"bridge": InternetExchange, "filter": ("ix", "ix_id")},
    }


class InternetExchangePrefix(Ixctl):
    class Meta(Ixctl.Meta):
        ref_tag = "prefix"
        data_object_cls = InternetExhangePrefixObject


class InternetExchangeMemberObject(IxctlEntity):
    description = "Ixctl Exchange Member"
    relationships = {
        "net": {"bridge": pdbctl.Network, "filter": ("asn", "asn")},
        "ix": {"bridge": InternetExchange, "filter": ("ix", "ix_id")},
    }


class InternetExchangeMember(Ixctl):
    class Meta(Ixctl.Meta):
        ref_tag = "member"
        data_object_cls = InternetExchangeMemberObject

    def set_mac_address(self, asn:int, ip:str, macaddr_set:list[str], source):
        data = {"macaddr_set": macaddr_set, "source": source}

        ip = ipaddress.ip_interface(ip).ip

        self.put(f"data/member/sync/{asn}/{ip}/mac-address", data=data)

    def set_as_macro(self, asn, as_macro, source):
        data = {"as_macro": as_macro, "asn": asn, "source": source}
        self.put("data/member/sync/as-macro", data=data)

    def set_route_server_md5(self, asn, md5, member_ip, router_ip, source):
        data = {"md5": md5, "asn": asn, "source": source}

        member_ip = ipaddress.ip_interface(member_ip).ip
        router_ip = ipaddress.ip_interface(router_ip).ip

        self.put(f"data/member/sync/{asn}/{member_ip}/{router_ip}/md5", data=data)

    def traffic(self, pk:int, start_time:str|int=None, duration:int=None, step:int=None):
        params = {}
        if start_time:
            params["start_time"] = start_time

        if duration:
            params["duration"] = duration

        if step:
            params["step"] = step

        return self.get(
            f"data/member/{pk}/traffic",
            params=params,
        )

    def traffic_asn_pair(self, pk:int, asn_src:int, asn_dst:int, start_time:int, duration:int, step:int):
        return self.get(
            f"data/member/{pk}/traffic_asn_pair",
            params={
                "asn_src": asn_src,
                "asn_dst": asn_dst,
                "start_time": start_time,
                "duration": duration,
                "step": step,
            },
        )

class RouteserverObject(IxctlEntity):
    description = "Ixctl Route Server"
    relationships = {
        "ix": {"bridge": InternetExchange, "filter": ("ix", "ix_id")},
    }


class Routeserver(Ixctl):
    class Meta(Ixctl.Meta):
        ref_tag = "routeserver"
        data_object_cls = RouteserverObject
