from common.models import HandleRefModel
from django.core.validators import RegexValidator
from django.db import models
from django.utils.translation import gettext_lazy as _
from django_grainy.decorators import grainy_model

SERVICE_ID_VALIDATOR = RegexValidator(
    regex=r"^[a-z0-9_]+$",
    message=_("service_id must contain only lowercase letters, digits, or underscores"),
)


@grainy_model(
    namespace="oauth_config",
    namespace_instance="oauth_config.{instance.service_id}",
)
class OAuthConfig(HandleRefModel):
    """
    OAuth client configuration looked up at auth time by
    `account.social_strategy.DBStrategy`. Provides DB-backed values for
    the SOCIAL_AUTH_{SERVICE}_* settings python-social-auth would otherwise
    read from Django settings.
    """

    service_id = models.CharField(
        max_length=64,
        unique=True,
        validators=[SERVICE_ID_VALIDATOR],
        help_text=_(
            "Matches a python-social-auth backend name (e.g. 'peeringdb', "
            "'google_oauth2'), lowercased with dashes replaced by underscores."
        ),
    )
    key = models.CharField(max_length=255, blank=True)
    secret = models.CharField(max_length=255, blank=True)
    tenant_id = models.CharField(
        max_length=255,
        blank=True,
        help_text=_(
            "Per-deployment tenant/realm/issuer identifier (e.g. Microsoft Entra "
            "tenant GUID). Used by backends that build authority URLs from it."
        ),
    )
    authorization_url = models.URLField(blank=True)
    access_token_url = models.URLField(blank=True)
    profile_url = models.URLField(blank=True)
    access_token_method = models.CharField(
        max_length=8,
        default="POST",
        blank=True,
        choices=(("GET", "GET"), ("POST", "POST")),
    )
    default_scope = models.JSONField(default=list, blank=True)
    extra_data = models.JSONField(default=list, blank=True)

    class Meta:
        db_table = "account_oauth_config"
        verbose_name = _("OAuth Config")
        verbose_name_plural = _("OAuth Configs")

    class HandleRef:
        tag = "oauth_config"

    def __str__(self):
        return self.service_id
