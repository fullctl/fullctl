from django.core.exceptions import ValidationError
from django_devicectl.schema import OrganizationConfig

__all__ = ["validate_org_config"]


def validate_org_config(value):
    try:
        if value:
            OrganizationConfig(**value)
    except Exception as e:
        raise ValidationError(str(e))
