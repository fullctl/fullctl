"""
pydantic schema for audictl api posts
"""

import re
from functools import wraps
from typing import List, Optional, Union

from pydantic import BaseModel, HttpUrl

__all__ = ["Component", "RblsrvComponent", "ErrorDetails", "NoData", "DeviceConfigData"]

# Dictionary to store registered Pydantic models
MODEL_REGISTRY = {}


def register_model(pattern):
    """
    Decorator to register a Pydantic model with a regex pattern in the MODEL_REGISTRY.

    Args:
        pattern (str): The regex pattern to associate with the model class.

    Returns:
        Callable: The decorated class.
    """
    compiled_pattern = re.compile(pattern)

    def decorator(cls):
        # Add the compiled pattern and the model class to the registry
        MODEL_REGISTRY[compiled_pattern] = cls

        @wraps(cls)
        def wrapped(*args, **kwargs):
            return cls(*args, **kwargs)

        return wrapped

    return decorator


def get_model_from_registry(unique_id):
    """
    Retrieve a Pydantic model from the MODEL_REGISTRY based on a unique ID.

    Args:
        unique_id (str): The unique ID used to match the appropriate model.

    Returns:
        Type[BaseModel]: The matched Pydantic model class or None if no match found.
    """
    for pattern, model_cls in MODEL_REGISTRY.items():
        if pattern.match(unique_id):
            return model_cls
    return None


class Component(BaseModel):
    """
    Pydantic model for a Component.

    Attributes:
        name (str): The name of the component.
        url (HttpUrl): The URL associated with the component.
        kind (str): The type of the component.
        error (str): The error associated with the component.
        type, e.g., "dict", "sequential", "stacked" etc.
    """

    name: Union[str, None] = None
    id: Union[str, int]
    url: Union[HttpUrl, None] = None
    blob: Union[str, None] = None
    kind: str


class RblsrvComponent(BaseModel):
    """
    Pydantic model for a RblsrvComponent.

    Attributes:
        kind (str): The type of the component.
        load_date (str): The date the component was loaded.
        target (str): The prefix.
    """

    target: Union[str, None] = None
    load_date: Union[str, None] = None
    kind: str


class ErrorComponent(Component):
    """
    Pydantic model for a Component.

    Attributes:
        name (str): The name of the component.
        url (HttpUrl): The URL associated with the component.
        kind (str): The type of the component.
        error (str): The error associated with the component.
    """

    error: str = None


class ErrorDetails(BaseModel):
    """
    Pydantic model for error details.

    Attributes:
        message (str): The error message.
        components (List[Component]): A list of related components, default is an empty list.
    """

    message: str
    components: List[ErrorComponent] = list()
    url: Union[HttpUrl, None] = None


@register_model(r"^default$")
class NoData(BaseModel):
    pass


@register_model(r"^v0.1\/[^\/]+\/config\/.+$")
class DeviceConfigData(BaseModel):
    diff: Union[str, None] = None
    components: List[Component] = list()
    url: Union[HttpUrl, None] = None


@register_model(r"^v0.1\/[^\/]+\/traffic\/.+$")
class TrafficData(BaseModel):
    components: List[Component] = list()


@register_model(r"^v0.1\/[^\/]+\/rblsrv\/.+$")
class RblsrvData(BaseModel):
    components: List[RblsrvComponent] = list()


class ConfigLivenessComponent(BaseModel):
    """
    Pydantic model for a ConfigLivenessComponent.

    Attributes:
        id (str): The routeserver router id.
        kind (str): The type of the event i.e. 'bird_config_liveness'.
    """

    id: str
    kind: str


@register_model(r"^v0.1\/[^\/]+\/config\/+\/liveness\/[0-9\.]+$")
class ConfigLivenessData(BaseModel):
    components: List[ConfigLivenessComponent] = list()


class BGPSessionStateComponent(BaseModel):
    """
    Pydantic model for a BGP session state.
    Contains the peer stats data

    Attributes:
        up (bool): The status of the session.
        last_change (datetime): The last date the session was up or down
        state (str): The state of the session i.e. ['Established', 'Passive'].
        protocol (str): The protocol for the session - BGP
        name (str): The name of the session
        asn (str): The peer member asn
        address (str): The peer member ipv4 or ipv6 address
        routeserver_router_id (str): The source routeserver router id
        routeserver_hostname (str): The source routeserver hostname
        router_id (str): The peer member router id
    """

    up: bool
    last_change: str
    state: str
    protocol: str
    name: str
    asn: str
    address: str
    routeserver_router_id: str
    routeserver_hostname: str
    router_id: Optional[str] = None
    routes_imported: Optional[int] = 0
    routes_exported: Optional[int] = 0
    import_updates_received: Optional[int] = 0
    import_updates_rejected: Optional[int] = 0
    import_updates_filtered: Optional[int] = 0
    import_updates_ignored: Optional[int] = 0
    import_updates_accepted: Optional[int] = 0
    import_withdraws_received: Optional[int] = 0
    import_withdraws_rejected: Optional[int] = 0
    import_withdraws_ignored: Optional[int] = 0
    import_withdraws_accepted: Optional[int] = 0
    export_updates_received: Optional[int] = 0
    export_updates_rejected: Optional[int] = 0
    export_updates_filtered: Optional[int] = 0
    export_updates_accepted: Optional[int] = 0
    export_withdraws_received: Optional[int] = 0
    export_withdraws_accepted: Optional[int] = 0


@register_model(r"^v0.1\/[^\/]+\/bgp\/stat\/[0-9\.]+\/[0-9]+$")
class BGPSessionStateData(BaseModel):
    components: List[BGPSessionStateComponent] = list()


class BGPSessionStateAggregateDataComponent(BaseModel):
    """
    Pydantic model for a bgp session state aggregate data.
    Contains the aggregate data for peer stats data

    Attributes:
        routeserver_router_id (int): The router id of the routeserver.
        routes_imported (int): The total number of routes imported
        routes_exported (int): The total number of routes exported
        established_connections_count (int): The total number of `Established` connections
        configured_connections_count (int): The total number of configured connections
        ip_version (str): The ip version that this aggregate is for i.e. ipv4, ipv6
        routeserver_hostname (str): The source routeserver hostname
    """

    routeserver_router_id: str
    routes_imported: int
    routes_exported: int
    established_connections_count: int
    configured_connections_count: int
    ip_version: str
    routeserver_hostname: str


@register_model(r"^v0.1\/[^\/]+\/bgp\/stat\/aggregate\/[0-9\.]+$")
class BGPSessionStateAggregateData(BaseModel):
    components: List[BGPSessionStateAggregateDataComponent] = list()
