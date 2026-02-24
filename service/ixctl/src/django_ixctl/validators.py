# import ipaddress
# from django.core.exceptions import ValidationError
# from django.utils.translation import gettext_lazy as _

from django.core.exceptions import ValidationError
from django_ixctl.schema import InternetExchangeConfig

__all__ = ["validate_ix_config"]


def validate_ix_config(value):
    try:
        if value:
            InternetExchangeConfig(**value)
    except Exception as e:
        raise ValidationError(str(e))
