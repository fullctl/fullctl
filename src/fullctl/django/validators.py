import ipaddress
import re

from django.core.exceptions import ValidationError


def validate_alphanumeric(value):
    """
    validates a value to only contain alphanumeric characters, dashes
    or underscores

    Argument(s):

        - value(str)

    Raises:

        - ValidationError: on failed validation
    """

    if re.search("[^a-zA-Z0-9-_]", value):
        raise ValidationError("value can only contain a-Z, 0-9, ,- ,_")


def validate_alphanumeric_list(value):
    """
    validates a list to only contain alphanumeric characters, dashes
    or underscores

    Argument(s):

        - value(list|str): if a str is supplied, it will be split using `,`
          as a separator

    Raises:

        - ValidationError: on failed validation
    """

    if not isinstance(value, list):
        value = value.split(",")

    for item in value:
        validate_alphanumeric(item)


def ip_address_string(value):
    """
    Takes an ip address string and returns a validated normalized
    ip address string.

    This will strep the net mask if it is provided
    """

    if not value:
        return value
    value = str(value)
    return str(ipaddress.ip_interface(value))
