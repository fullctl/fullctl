from django import template
from django.utils.translation import gettext_lazy as _
from django_otp.plugins.otp_email.models import EmailDevice
from django_otp.plugins.otp_totp.models import TOTPDevice

register = template.Library()


@register.filter
def device_action(device):
    if isinstance(device, EmailDevice):
        return _("Email one time password")
    if isinstance(device, TOTPDevice):
        return _("Authenticator app")
    if device:
        try:
            if device.method == "security-key":
                return _("U2F security key")
        except AttributeError:
            pass


@register.filter
def social_id(user, backend_name):
    data = user.social_auth.filter(provider=backend_name).first()
    if not data:
        return ""
    if backend_name == "peeringdb":
        # peeringdb does not provide email or username as uid
        # but rather the actual user id - display email instead
        return data.extra_data.get("email")

    return data.uid
