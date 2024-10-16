import json
import re
from datetime import timedelta
from functools import wraps

import fullctl.service_bridge.devicectl as devicectl
import fullctl.service_bridge.ixctl as ixctl
from django.conf import settings
from fullctl.django.mail import send_plain
from fullctl.service_bridge.client import url_join

import django_auditctl.models.auditctl as models
from django_auditctl.rest.serializers.auditctl import Serializers
from django_auditctl.util import object_id_to_parts
import django_auditctl.schema as schema
from django_auditctl.metrics import Metric
from fullctl.metrics import Metrics

import structlog

__all__ = [
    "register_handler",
    "get_handlers",
    "get_handler_by_tag",
]

log = structlog.get_logger(__name__)

# Dictionary to store event handlers
HANDLER_REGISTRY = {}


def register_handler(pattern):
    """
    A decorator function that registers a handler class to handle events matching the given pattern.

    Args:
    - pattern (str): A regular expression pattern to match events.

    Returns:
    - decorator (callable): A decorator function that adds the decorated class to the HANDLER_REGISTRY dictionary.
    """
    compiled_pattern = re.compile(pattern)

    def decorator(cls):
        # Add the compiled pattern and the model class to the registry
        HANDLER_REGISTRY[compiled_pattern] = cls

        @wraps(cls)
        def wrapped(*args, **kwargs):
            return cls(*args, **kwargs)

        return wrapped

    return decorator


def get_handlers(event):
    """
    A generator function that searches the HANDLER_REGISTRY for matching event handler classes and yields instances for them.

    Args:
    - event (auditctl.Event): An audictl event instance  to be handled.

    Yields:
    - handler_cls(event) (object): An instance of the matching event handler class.
    """
    for pattern, handler_cls in HANDLER_REGISTRY.items():
        if pattern.match(event.object_id):
            yield handler_cls(event)


def get_handler_by_tag(tag):
    """
    A function that searches the HANDLER_REGISTRY for a matching event handler class by tag.

    Args:
    - tag (str): The tag of the event handler class to be retrieved.

    Returns:
    - handler_cls (object): The matching event handler class.
    """
    for handler_cls in HANDLER_REGISTRY.values():
        if handler_cls.HandleRef.tag == tag:
            return handler_cls
    return None


class BaseHandler:
    """
    A base class for event handler classes. Raises a NotImplementedError when called.
    """

    class Heartbeat:
        interval = timedelta(seconds=settings.HEARTBEAT_EXPECTED_INTERVAL)

    class HandleRef:
        tag = "base_handler"

    @property
    def previous_status(self):
        """
        Returns the previous status of the event identified by the object_id.
        """
        try:
            return (
                models.Event.objects.filter(
                    object_id=self.event.object_id, created__lt=self.event.created
                )
                .latest("created")
                .status
            )
        except models.Event.DoesNotExist:
            return None

    @property
    def qualifies(self):
        return True

    @property
    def schema(self) -> schema.EventData:
        """
        Returns the schema for the event object_id.
        """

        if hasattr(self, "_schema"):
            return self._schema

        self._schema = schema.get_model_from_registry(self.event.object_id)

        return self._schema

    def __init__(self, event):
        self.event = event

    def __call__(self):
        raise NotImplementedError

    def heartbeat(self):
        object_id = self.event.object_id
        heartbeat, created = models.Heartbeat.objects.get_or_create(object_id=object_id)
        if not created:
            heartbeat.save()
        else:
            heartbeat.interval = self.Heartbeat.interval
            heartbeat.save()


@register_handler(r"^v0.1\/[^\/]+\/.+$")
class EmailAlert(BaseHandler):

    """
    A class that inherits from the BaseHandler class and sends email alerts on error events.

    Recipient addresses will be grabbed from the OrganizationEmailAlert model.
    """

    class HandleRef:
        tag = "email_alert"

    @property
    def qualifies(self):
        return self.previous_status in ["ok", None] and self.event.status == "error"

    def __call__(self):
        """
        Sends an email alert if the event status goes from ok to error
        """

        if self.qualifies:
            error_message = self.event.error.get("message")
            id_parts = object_id_to_parts(self.event.object_id)
            org_tag = id_parts.get("org_tag")

            serializer = Serializers.event(instance=self.event)
            components = json.dumps(serializer.data, indent=2)
            event_url = (
                url_join(settings.AUDITCTL_URL, org_tag)
                + f"?q={id_parts['ref_tag']}/{id_parts['ref_id']}&error=true"
            )
            email_addresses = [
                alert.email
                for alert in models.OrganizationEmailAlert.objects.filter(
                    org__slug=org_tag
                )
                if alert.enabled
            ]

            send_plain(
                f"Error: {self.event.object_id}",
                f"{error_message}\n{event_url}\n\n{components}",
                settings.DEFAULT_FROM_EMAIL,
                email_addresses,
            )


class ForwardToService(BaseHandler):
    """
    A class that inherits from the BaseHandler class and forwards events to a service.
    """

    pass


@register_handler(r"^v0.1\/[^\/]+\/config\/device.+$")
class DeviceOperationalStatus(ForwardToService):

    """
    A class that inherits from the ForwardToService class and handles device operational status events.
    """

    class HandleRef:
        tag = "devicectl_device_operational_status"

    def __call__(self):
        """
        Calls the set_operational_status method of the devicectl Device class for each component in the event.
        """

        self.heartbeat()

        if self.event.status == "ok":
            components = self.event.data.get("components", [])
            error_message = None
        elif self.event.status == "error":
            components = self.event.error.get("components", [])
            error_message = self.event.error.get("message")
        else:
            return

        device = devicectl.Device()

        status_updates = {}
        reports = []

        for component in components:
            kind = component.get("kind")
            id = component.get("id")

            status_updates.setdefault(id, {})

            if kind == "device":
                if self.event.status == "error":
                    device_error_message = f"{error_message}\n\n{component['error']}"
                else:
                    device_error_message = None

                status_updates[id].update(
                    error_message=device_error_message,
                    status=self.event.status,
                    event=str(self.event.id),
                    device_id=id,
                )

            elif kind == "current-config":
                status_updates[id].update(
                    url_current=component.get("url"),
                    config_current=component.get("blob", ""),
                )

            elif kind == "reference-config":
                status_updates[id].update(
                    url_reference=component.get("url"),
                    config_reference=component.get("blob", ""),
                )
            elif kind == "report":
                reports.append(dict(id=id, report=component.get("blob", "")))

        for _, update in status_updates.items():
            if not update:
                continue
            device.set_operational_status(**update)

        for report in reports:
            device.push_referee_report(report["id"], report["report"])


@register_handler(r"^v0.1\/[^\/]+\/traffic\/.+$")
class TrafficHandler(BaseHandler):
    class Heartbeat:
        interval = timedelta(seconds=settings.HEARTBEAT_EXPECTED_INTERVAL_TRAFFIC)

    class HandleRef:
        tag = "devicectl_traffic"

    def __call__(self):
        self.heartbeat()


@register_handler(r"^v0.1\/[^\/]+\/rblsrv\/.+$")
class RblsrvDataHandler(BaseHandler):
    """
    Handles Alerting Rblsrv Data events
    """

    def __call__(self):
        pass


@register_handler(r"^v0.1\/[^\/]+\/config\/liveness\/[0-9\.]+$")
class ConfigLivenessDataHandler(BaseHandler):
    """
    Handles Config Liveness Data events
    """

    class HandleRef:
        tag = "config_liveness"

    def __call__(self):
        self.heartbeat()


@register_handler(r"^v0.1\/[^\/]+\/bgp\/stat\/[0-9\.]+\/[0-9]+$")
class BGPSessionStateDataHandler(BaseHandler):
    """
    Handles BGP Sesssion State Data events
    """

    class HandleRef:
        tag = "bgp_stat"

    def __call__(self):
        self.heartbeat()
        components = self.event.data.get("components", [])
        member_bridge = ixctl.InternetExchangeMember()
        for component in components:
            member_bridge.set_event_reference(
                asn=component.get("asn"),
                address=component.get("address"),
                routeserver_router_id=component.get("routeserver_router_id"),
                event_reference=self.event.id,
            )


@register_handler(r"^v0.1\/[^\/]+\/bgp\/stat\/aggregate\/[0-9\.]+$")
class BGPSessionStateAggregateDataHandler(BaseHandler):
    """
    Handles BGP Session State Aggregate Data events
    """

    class HandleRef:
        tag = "bgp_stat_aggregate"

    def __call__(self):
        self.heartbeat()
        components = self.event.data.get("components", [])
        routeserver = ixctl.Routeserver()
        component = components[0]
        routeserver.set_event_reference(
            component.get("routeserver_router_id"), self.event.id
        )


@register_handler(r"^v0.1\/[^\/]+\/.+$")
class InsertMetrics(BaseHandler):
    """
    A class that inherits from the BaseHandler class and inserts
    metrics for events.
    """

    class HandleRef:
        tag = "insert_metrics"

    @property
    def qualifies(self):

        if not settings.EVENT_METRICS_ENABLED:
            return False

        if not settings.TIMESERIES_DB_URL:
            log.warning(
                "TIMESERIES_DB_URL not set, skipping metrics insertion, set EVENT_METRICS_ENABLED to False to disable this warning"
            )
            return False

        try:
            return self.schema.metrics_enabled()
        except AttributeError:
            if not self.schema:
                return False
            log.warning(f"metrics_enabled not implemented for {self.schema.__name__}")
            return False

    def __call__(self):
        """
        Inserts metrics for the event.
        """

        if not self.qualifies:
            return

        auth = (
            (settings.TIMESERIES_DB_USER, settings.TIMESERIES_DB_PASSWORD)
            if settings.TIMESERIES_DB_USER
            else None
        )

        metrics_client = Metrics(settings.TIMESERIES_DB_URL, auth=auth)

        metric_data = self.schema.get_metric_fields_and_tags(self.event)

        if not isinstance(metric_data, list):
            metric_data = [metric_data]

        for metric in metric_data:
            self.insert_metric(metric, metrics_client)

    def insert_metric(self, metric_data: dict, metrics_client: Metrics):

        if not metric_data:
            log.warning(
                f"get_metric_fields_and_tags returned None for {self.event.object_id} ({self.event.id})"
            )
            return

        if not isinstance(metric_data, Metric):
            log.warning(
                f"get_metric_fields_and_tags did not return a Metric instance for {self.event.object_id} ({self.event.id})"
            )
            return

        if not metric_data.fields:
            log.warning(
                f"No metrics (fields) in MetricsMeta instance for {self.event.object_id} ({self.event.id}) returned by get_metric_fields_and_tags"
            )
            return

        # require ctl_org_id and ctl_object_id in tags

        if "ctl_org_id" not in metric_data.tags:
            metric_data.tags["ctl_org_id"] = self.event.org_id

        if "ctl_object_id" not in metric_data.tags:
            metric_data.tags["ctl_object_id"] = self.event.object_id

        log.info(
            f"Inserting metrics for {self.event.object_id}", metric_data=metric_data
        )

        metrics_client.write_many(
            [
                {
                    "measurement": f"{settings.EVENT_METRIC_PREFIX}{metric_data.name}",
                    "fields": metric_data.fields,
                    "tags": metric_data.tags,
                    # to seconds
                    "timestamp": int(self.event.created.timestamp()),
                }
            ]
        )
