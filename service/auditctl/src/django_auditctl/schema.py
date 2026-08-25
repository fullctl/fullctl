"""
pydantic schema for audictl api posts
"""

import re
from functools import wraps
from typing import Annotated, List, Optional, Union

from django_auditctl.metrics import (
    ComponentFields,
    ComponentTags,
    Metric,
    MetricsMixin,
    MetricsMultiComponentMixin,
    MetricsSelectiveComponentMixin,
)
from django_auditctl.models.auditctl import Event
from pydantic import BaseModel, BeforeValidator, Field, HttpUrl, TypeAdapter

__all__ = ["Component", "RblsrvComponent", "ErrorDetails", "NoData", "DeviceConfigData"]

# Dictionary to store registered Pydantic models
MODEL_REGISTRY = {}

HttpUrlTypeAdapter = TypeAdapter(HttpUrl)
Url = Annotated[
    str,
    BeforeValidator(lambda value: HttpUrlTypeAdapter.validate_python(value) and value),
]


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


def get_event_data(event: Event, schema_cls: BaseModel) -> BaseModel | None:
    """
    Convert an Event object to a Pydantic model.

    Args:
        event (Event): The Event object to convert.
        schema_cls (BaseModel): The Pydantic model class to convert the Event object to.

    Returns:
        BaseModel: The Pydantic model object.
        None: If the event has no data or error.
    """
    if event.data:
        return schema_cls(**event.data)
    elif event.error:
        return ErrorDetails(**event.error)
    else:
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

    name: str | None = None
    id: str | int | None = None
    url: Url | None = None
    blob: str | None = None
    kind: str


class RblsrvComponent(BaseModel):
    """
    Pydantic model for a RblsrvComponent.

    Attributes:
        kind (str): The type of the component.
        load_date (str): The date the component was loaded.
        target (str): The prefix.
    """

    target: str | None = None
    load_date: str | None = None
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

    error: str | None = None


class ErrorDetails(BaseModel):
    """
    Pydantic model for error details.

    Attributes:
        message (str): The error message.
        components (List[Component]): A list of related components, default is an empty list.
    """

    message: str
    components: list[ErrorComponent] = list()
    url: Url | None = None


class EventData(BaseModel, MetricsMixin):

    @classmethod
    def error_schema(cls) -> ErrorDetails:
        return ErrorDetails

    @classmethod
    def get_event_data(cls, event: Event) -> BaseModel | None:
        return get_event_data(event, cls)


@register_model(r"^default$")
class NoData(EventData):
    pass


class ApiActionRequest(Component):
    """
    Pydantic model for an ApiActionRequest.

    Attributes:
        method (str): The HTTP method of the request.
    """

    username: str
    action: str
    payload: dict
    service: str
    ref_tag: str
    kind: str = "request"


class ApiActionResponse(Component):
    """
    Pydantic model for an ApiActionResponse.

    Attributes:
        status_code (int): The HTTP status code of the response.
    """

    status_code: int
    kind: str = "response"


class ApiActionErrorDetails(ErrorDetails):
    """
    Pydantic model for an ApiActionErrorDetails.

    Attributes:
        message (str): The error message.
        components (List[Component]): A list of related components, default is an empty list.
    """

    components: list[ApiActionRequest | ApiActionResponse] = Field(default_factory=list)


# log service api actions (create, delete, update)
@register_model(r"v0.1\/[^\/]+\/action\/.+$")
class ApiActionData(EventData):
    components: list[ApiActionRequest | ApiActionResponse] = Field(default_factory=list)

    @classmethod
    def error_schema(cls) -> ApiActionErrorDetails:
        return ApiActionErrorDetails

    @classmethod
    def metrics_enabled(cls) -> bool:
        # TODO: do we want to emit metrics for this event?
        return False


@register_model(r"^v0.1\/[^\/]+\/config\/.+$")
class DeviceConfigData(EventData, MetricsSelectiveComponentMixin):
    diff: str | None = None
    components: list[Component] = list()
    url: Url | None = None

    @classmethod
    def metric_name(cls) -> str:
        return "device_config"

    @classmethod
    def metric_tags(cls) -> list[ComponentTags]:
        return [ComponentTags(kind="device", tags=["id", "name"])]


@register_model(r"^v0.1\/[^\/]+\/traffic\/.+$")
class TrafficData(EventData, MetricsSelectiveComponentMixin):
    components: list[Component] = list()

    @classmethod
    def metric_name(cls) -> str:
        return "traffic"

    @classmethod
    def metric_tags(cls) -> list[ComponentTags]:
        return [ComponentTags(kind="ix", tags=["id", "name"])]


@register_model(r"^v0.1\/[^\/]+\/rblsrv\/.+$")
class RblsrvData(EventData, MetricsSelectiveComponentMixin):
    components: list[RblsrvComponent] = list()

    @classmethod
    def metric_name(cls) -> str:
        return "rblsrv"

    @classmethod
    def metric_tags(cls) -> list[ComponentTags]:
        return [ComponentTags(kind="prefix", tags=["target"])]


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
class ConfigLivenessData(EventData):
    components: list[ConfigLivenessComponent] = list()

    @classmethod
    def metric_name(cls) -> str:
        return "config_liveness"


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
    router_id: str | None = None
    routes_imported: int | None = 0
    routes_exported: int | None = 0
    import_updates_received: int | None = 0
    import_updates_rejected: int | None = 0
    import_updates_filtered: int | None = 0
    import_updates_ignored: int | None = 0
    import_updates_accepted: int | None = 0
    import_withdraws_received: int | None = 0
    import_withdraws_rejected: int | None = 0
    import_withdraws_ignored: int | None = 0
    import_withdraws_accepted: int | None = 0
    export_updates_received: int | None = 0
    export_updates_rejected: int | None = 0
    export_updates_filtered: int | None = 0
    export_updates_accepted: int | None = 0
    export_withdraws_received: int | None = 0
    export_withdraws_accepted: int | None = 0


class BGPStatBase(EventData, MetricsMultiComponentMixin):
    components: list[BGPSessionStateComponent] = list()

    @classmethod
    def metric_name(cls) -> str:
        return "bgp_stat"

    @classmethod
    def metric_tags(cls) -> list[ComponentTags] | list[str]:

        return [
            "routeserver_router_id",
            "routeserver_hostname",
            "router_id",
            "name",
            "asn",
            "address",
            "protocol",
            "state",
        ]

    @classmethod
    def metric_fields(cls) -> list[ComponentFields] | list[str]:

        return [
            "up",
            "routes_imported",
            "routes_exported",
            "import_updates_received",
            "import_updates_rejected",
            "import_updates_filtered",
            "import_updates_ignored",
            "import_updates_accepted",
            "import_withdraws_received",
            "import_withdraws_rejected",
            "import_withdraws_ignored",
            "import_withdraws_accepted",
            "export_updates_received",
            "export_updates_rejected",
            "export_updates_filtered",
            "export_updates_accepted",
            "export_withdraws_received",
            "export_withdraws_accepted",
        ]


@register_model(r"^v0.1\/[^\/]+\/bgp\/stat\/[0-9\.]+\/[0-9]+$")
class BGPSessionStateData(BGPStatBase):
    pass


@register_model(r"^v0.2\/[^\/]+\/bgp\/stat\/[0-9\.]+$")
class BatchedBGPSessionStateData(BGPStatBase):
    pass


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
class BGPSessionStateAggregateData(EventData, MetricsSelectiveComponentMixin):
    components: list[BGPSessionStateAggregateDataComponent] = list()

    @classmethod
    def metric_name(cls) -> str:
        return "bgp_stat_aggregate"

    @classmethod
    def metric_tags(cls) -> list[ComponentTags] | list[str]:
        return [
            "routeserver_router_id",
            "routeserver_hostname",
            "ip_version",
        ]

    @classmethod
    def metric_fields(cls) -> list[ComponentFields] | list[str]:
        return [
            "routes_imported",
            "routes_exported",
            "established_connections_count",
            "configured_connections_count",
        ]


class TrafficAlertNotificationComponent(BaseModel):
    """
    Pydantic model for a Traffic Alert Notification.

    Attributes:
        id (str): The id of the notification.
        kind (str): The type of notification i.e. 'email'.
        subject (str): The notification subject.
        message (str): The notification message.
        recipients (list[str]): The list of notification recipients.
    """

    id: str
    kind: str
    subject: str
    message: str
    recipients: list[str]


@register_model(r"^v0.1\/[^\/]+\/notification\/+\/traffic_alert\/$")
class TrafficAlertNotificationData(EventData):
    components: list[TrafficAlertNotificationComponent] = list()

    @classmethod
    def metric_name(cls) -> str:
        return "traffic_alert_notification"
