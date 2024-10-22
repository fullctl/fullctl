import reversion
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext as _

from account.models import Organization
from common.models import HandleRefModel


def validate_logo_url_formatting(value):
    if value:
        urlvars = {
            "version": settings.PACKAGE_VERSION,
            "static_path": settings.STATIC_URL,
        }
        try:
            value.format(**urlvars)
        except KeyError as e:
            raise ValidationError(
                f"Unknown variable: {e}. Allowed variables are `version` and `static_path`"
            )


@reversion.register
class OrganizationBranding(HandleRefModel):
    org = models.OneToOneField(Organization, on_delete=models.CASCADE)
    html_footer = models.TextField(blank=True, null=True)
    css = models.JSONField(default=dict, blank=True)
    dark_logo_url = models.URLField(
        _("Dark Background Logo URL"),
        max_length=2000,
        blank=True,
        null=True,
        help_text=_("URL used to display the dark logo on the dashboard."),
        validators=[validate_logo_url_formatting],
    )
    light_logo_url = models.URLField(
        _("White Backround Logo URL"),
        max_length=2000,
        blank=True,
        null=True,
        help_text=_("URL used to display the light logo on the dashboard."),
        validators=[validate_logo_url_formatting],
    )
    favicon_url = models.URLField(
        _("Favicon URL"),
        max_length=2000,
        blank=True,
        null=True,
        help_text=_("URL used to display the favicon on the application."),
        validators=[validate_logo_url_formatting],
    )
    show_logo = models.BooleanField(
        default=False, help_text=_("Show logo in the services drop down")
    )
    http_host = models.CharField(
        _("HTTP Host"),
        max_length=255,
        blank=True,
        null=True,
        help_text=_("The HTTP host used to display the branding."),
    )

    class HandleRef:
        tag = "org_branding"

    def __str__(self):
        return f"{self.org.name}'s Branding"
