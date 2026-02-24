import pydantic
import reversion
from account.models import Organization
from common.models import HandleRefModel
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext as _


class OrganizationBrandingDataObject(pydantic.BaseModel):
    name: str
    html_footer: str
    css: dict
    dark_logo_url: str
    light_logo_url: str
    favicon_url: str
    show_logo: bool

    @property
    def org_name(self) -> str:
        return self.name


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


def format_branding_url(url: str) -> str:
    if url:
        urlvars = {
            "version": settings.PACKAGE_VERSION,
            "static_path": settings.STATIC_URL,
        }
        return url.format(**urlvars)

    return url


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

    def serialize(self) -> OrganizationBrandingDataObject:
        return OrganizationBrandingDataObject(
            **{
                "name": self.org.name,
                "html_footer": self.html_footer,
                "css": self.css,
                "dark_logo_url": format_branding_url(self.dark_logo_url),
                "light_logo_url": format_branding_url(self.light_logo_url),
                "favicon_url": format_branding_url(self.favicon_url),
                "show_logo": self.show_logo,
            }
        )
