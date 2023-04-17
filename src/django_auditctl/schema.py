"""
pydantic schema for audictl api posts
"""

import ipaddress
import re
from functools import wraps
from typing import List, Union

from pydantic import BaseModel, HttpUrl

__all__ = [
    "Component",
    "ErrorDetails",
    "NoData",
    "ConfigRouteServerData",
]

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
        type (str): The type of the component.
        error (str): The error associated with the component.
    """

    name: str
    url: HttpUrl
    type: str
    error: str


class ErrorDetails(BaseModel):
    """
    Pydantic model for error details.

    Attributes:
        message (str): The error message.
        components (List[Component]): A list of related components, default is an empty list.
    """

    message: str
    components: List[Component] = list()


@register_model(r"^default$")
class NoData(BaseModel):
    pass


@register_model(r"^v0.1-[^-]+-config-routeserver-.+$")
class ConfigRouteServerData(BaseModel):
    ip: Union[ipaddress.IPv4Address, ipaddress.IPv6Address]

    def dict(self, *args, **kwargs):
        r = super().dict(*args, **kwargs)
        r["ip"] = str(self.ip)
        return r
