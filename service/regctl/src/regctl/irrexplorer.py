"""
Functions to fetch and parse data from IRRexplorer
"""

import pydantic
import httpx

URL_ASN = "https://irrexplorer.nlnog.net/api/prefixes/asn/{asn}"
URL_PREFIX = "https://irrexplorer.nlnog.net/api/prefixes/prefix/{prefix}"

# Schema

class Source(pydantic.BaseModel):
    url: str

class Message(pydantic.BaseModel):
    text: str
    category: str

class Route(pydantic.BaseModel):
    rpslText: str
    asn: int
    rpkiStatus: str
    rpkiMaxLength: int | None = None
    rpslPk: str

class PrefixInfo(pydantic.BaseModel):
    prefixSortKey: str
    prefix: str
    rir: str
    bgpOrigins: list[int] = pydantic.Field(default_factory=list)
    categoryOverall: str
    goodnessOverall: int
    rpkiRoutes: list[Route] = pydantic.Field(default_factory=list)
    messages: list[Message] = pydantic.Field(default_factory=list)
    irrRoutes: dict[str, list[Route]] = pydantic.Field(default_factory=dict)

class ASNRoutingData(pydantic.BaseModel):
    directOrigin: list[PrefixInfo] = pydantic.Field(default_factory=list)
    overlaps: list[PrefixInfo] = pydantic.Field(default_factory=list)
    source: Source | None = None

class PrefixRoutingData(pydantic.BaseModel):
    prefixes: list[PrefixInfo]
    source: Source | None = None

# fetchers

async def get_asn_routing_data(asn: int | str) -> ASNRoutingData:

    """
    Requests routing data for a given ASN from IRRexplorer

    Arguments:

    - `asn` (int | str): The ASN to look up

    Returns:

    - `ASNRoutingData`: The routing data for the given ASN
    """

    async with httpx.AsyncClient() as client:
        url = URL_ASN.format(asn=asn)
        response = await client.get(url)
        response.raise_for_status()
        return ASNRoutingData(source=Source(url=url), **response.json())

async def get_prefix_routing_data(prefix: str) -> PrefixRoutingData:

    """
    Requests routing data for a given prefix from IRRexplorer

    Arguments:

    - `prefix` (str): The prefix to look up

    Returns:

    - `PrefixRoutingData`: The routing data for the given prefix
    """

    async with httpx.AsyncClient() as client:
        url = URL_PREFIX.format(prefix=prefix)
        response = await client.get(url)
        response.raise_for_status()
        return PrefixRoutingData(source=Source(url=url), prefixes=[PrefixInfo(**item) for item in response.json()])