import json
import re
from functools import wraps

import fullctl.service_bridge.devicectl as devicectl
from django.conf import settings
from fullctl.django.mail import send_plain

import django_auditctl.models.auditctl as models

__all__ = [
    "register_handler",
    "get_handlers",
    "get_handler_by_tag",
]

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

    class HandleRef:
        tag = "base_handler"

    def __init__(self, event):
        self.event = event

    def __call__(self):
        raise NotImplementedError


@register_handler(r"^v0.1-[^-]+-.+$")
class EmailAlert(BaseHandler):

    """
    A class that inherits from the BaseHandler class and sends email alerts on error events.

    Recipient addresses will be grabbed from the OrganizationEmailAlert model.
    """

    class HandleRef:
        tag = "email_alert"

    def __call__(self):
        """
        Sends an email alert if the event status is error
        """

        if self.event.status == "error":
            error_message = self.event.error.get("message")
            org_slug = self.event.object_id.split("-")[1]
            components = json.dumps(self.event.error.get("components", []), indent=2)
            email_addresses = [
                alert.email
                for alert in models.OrganizationEmailAlert.objects.filter(
                    org__slug=org_slug
                )
                if alert.enabled
            ]

            send_plain(
                f"Error: {self.event.object_id}",
                f"{error_message}\n\n{components}",
                settings.DEFAULT_FROM_EMAIL,
                email_addresses,
            )


class ForwardToService(BaseHandler):
    """
    A class that inherits from the BaseHandler class and forwards events to a service.
    """

    pass


@register_handler(r"^v0.1-[^-]+-config-device.+$")
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
        if self.event.status == "ok":
            components = self.event.data.get("components", [])
            error_message = None
        elif self.event.status == "error":
            components = self.event.error.get("components", [])
            error_message = self.event.error.get("message")
        else:
            return

        device = devicectl.Device()

        for _device in components:
            if self.event.status == "error":
                device_error_message = f"{error_message}\n\n{_device['error']}"
            else:
                device_error_message = None

            device.set_operational_status(
                device_id=_device["id"],
                status=self.event.status,
                event=str(self.event.id),
                error_message=device_error_message,
            )
