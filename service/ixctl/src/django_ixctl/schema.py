import ipaddress

import pydantic

__all__ = [
    "InternetExchangeMemberMetaData",
    "InternetExchangeConfig",
    "IXLanConfig",
]


class InternetExchangeMemberMetaData(pydantic.BaseModel):
    case_number: list[str | int] | None = None

    # Arbitrary custom key-value store for information that does not have a dedicated
    # field in ixctl. Each key must be a string and the value must be a scalar that
    # can be represented in JSON (str, int, float or bool).
    custom: dict[str, str | int | float | bool] | None = None


class InternetExchangeConfig(pydantic.BaseModel):
    port_sizes: list[int] = pydantic.Field(default_factory=list)
    facilities: list[str] = pydantic.Field(default_factory=list)
    ixf_id: int = 0


class IXLanConfig(pydantic.BaseModel):
    mtu: int | None = None
    prefixes: list[pydantic.IPvAnyNetwork] = pydantic.Field(default_factory=list)

    def get_ip4_prefixes(self) -> list[ipaddress.IPv4Network]:
        return [
            ipaddress.IPv4Network(prefix)
            for prefix in self.prefixes
            if ipaddress.ip_network(prefix).version == 4
        ]

    def get_ip6_prefixes(self) -> list[ipaddress.IPv6Network]:
        return [
            ipaddress.IPv6Network(prefix)
            for prefix in self.prefixes
            if ipaddress.ip_network(prefix).version == 6
        ]
