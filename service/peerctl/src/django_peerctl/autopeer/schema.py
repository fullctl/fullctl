from typing import Optional

from pydantic import BaseModel


class Location(BaseModel):
    id: str
    type: str


class Locations(BaseModel):
    items: list[Location]
    requestId: str


class Session(BaseModel):
    """
    Session schema from the openapi definition
    """

    # TODO most optional for now, but should be adjusted
    # according to openapi schema

    peer_asn: str
    peer_ip: str
    location: Location

    # allowed values?
    peer_type: str | None = "peer"
    md5: str | None = ""
    local_asn: int | None = 0
    local_ip: str | None = ""

    # allowed values?
    status: str | None = ""

    uuid: str | None = ""
