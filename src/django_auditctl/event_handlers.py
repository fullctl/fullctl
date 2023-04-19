from functools import wraps
import fullctl.service_bridge.devicectl as devicectl
import re

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
    for pattern, handler_cls in HANDLER_REGISTRY.items():
        if handler_cls.HandleRef.tag == tag:
            return handler_cls
    return Nonedevice


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
        Overrides the __call__ method of the BaseHandler class.
        Calls the set_operational_status method of the devicectl Device class for each component in the event.
        """
        if self.event.status == "ok":
            components = self.event.data.get("components",[])
        elif self.event.status == "error":
            components = self.event.error.get("components",[])
        else:
            return
    
        print("components", components)

        device = devicectl.Device()

        for _device in components:

            device.set_operational_status(
                device_id=_device["id"],
                status=self.event.status,
                event=str(self.event.id),
                error_message=None,
            )