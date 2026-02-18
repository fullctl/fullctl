from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


def validate_password(value):
    required_length = settings.VALIDATE_PASSWORD_LENGTH

    if len(value) < required_length:
        raise ValidationError(
            _(
                "Password needs to be at least {} characters long".format(
                    required_length
                )
            )
        )

    return value
