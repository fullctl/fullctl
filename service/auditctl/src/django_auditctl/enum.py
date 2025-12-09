from django.utils.translation import gettext_lazy as _

__all__ = ["STATUS"]

STATUS = (
    ("ok", _("OK")),
    ("error", _("Error")),
)
