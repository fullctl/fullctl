import pydantic

__all__ = [
    "InternetExchangeMemberMetaData",
    "InternetExchangeConfig",
    "IXLanConfig",
]


class InternetExchangeMemberMetaData(pydantic.BaseModel):
    case_number: list[str | int] | None = None


class InternetExchangeConfig(pydantic.BaseModel):
    port_sizes: list[int] = pydantic.Field(default_factory=list)


class IXLanConfig(pydantic.BaseModel):
    mtu: int | None = None
    prefixes: list[pydantic.IPvAnyNetwork] = pydantic.Field(default_factory=list)
