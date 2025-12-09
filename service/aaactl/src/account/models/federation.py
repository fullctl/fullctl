import dataclasses
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.translation import gettext_lazy as _
from fullctl.django.models.abstract import HandleRefModel
from oauth2_provider.generators import generate_client_id, generate_client_secret
from oauth2_provider.models import Application


@dataclasses.dataclass
class AuthFederationInfo:
    client_id: str
    client_secret: str
    auth: "AuthFederation"


class AuthFederation(HandleRefModel):
    """
    A one to one relationship with the OAuth2 Application model to allow for organization ownership
    """

    org = models.ForeignKey(
        "account.Organization",
        on_delete=models.CASCADE,
        related_name="oauth_applications",
        verbose_name=_("Organization"),
    )

    application = models.OneToOneField(
        "oauth2_provider.Application",
        on_delete=models.CASCADE,
        related_name="organization",
        verbose_name=_("Application"),
    )

    class Meta:
        verbose_name = _("Federation for Organization")
        verbose_name_plural = _("Federation for Organization")
        unique_together = ("org", "application")
        db_table = "account_organization_oauth_application"

    class HandleRef:
        tag = "auth_federation"

    @classmethod
    def require_for_org(cls, org, user) -> AuthFederationInfo:
        """
        Ensure that an OAuth application exists for the organization

        Returns the AuthFederation instance, the client_id, and the client_secret

        The client secret will be returned hashed if the application did already exist
        """

        client_id = None
        client_secret = None

        try:
            auth = cls.objects.get(org=org)
            client_id = auth.application.client_id
            client_secret = auth.application.client_secret
            return AuthFederationInfo(client_id, client_secret, auth)
        except cls.DoesNotExist:
            return cls.create_for_org(org, user)

    @classmethod
    def create_for_org(cls, org, user) -> AuthFederationInfo:
        """
        Create an OAuth application for the organization

        Will return an AuthFederationInfo object with the client_id and client_secret and
        the AuthFederation instance.

        The client secret will be hashed in the database and this is the only time it will be available
        """

        # only one application per organization

        if cls.objects.filter(org=org).exists():
            raise ValidationError(
                _("An OAuth application already exists for this organization.")
            )

        client_id = generate_client_id()
        client_secret = generate_client_secret()

        app = Application.objects.create(
            name=org.name,
            redirect_uris="",
            client_type="confidential",
            authorization_grant_type="authorization-code",
            skip_authorization=False,
            user=user,
            client_id=client_id,
            client_secret=client_secret,
        )

        auth = cls.objects.create(org=org, application=app)

        return AuthFederationInfo(client_id, client_secret, auth)

    def __str__(self):
        return f"{self.org.name} OAuth Application"

    def set_redirect_urls(self):

        """
        Will compile the service urls for the organization and set them as the redirect urls for the application
        appending "/complete/twentyc/" to the end of each url first
        """

        urls = self.federated_service_urls.all()

        redirect_urls = [f"{url.url.rstrip('/')}/complete/twentyc/" for url in urls]
        self.application.redirect_uris = "\n".join(redirect_urls)
        self.application.save()

    def new_client_secret(self) -> AuthFederationInfo:
        """
        Generate a new client secret for the application
        """

        secret = generate_client_secret()
        self.application.client_secret = secret
        self.application.save()
        return AuthFederationInfo(self.application.client_id, secret, self)


class ServiceFederationSupport(HandleRefModel):
    slug = models.CharField(max_length=32, unique=True)
    name = models.CharField(max_length=255, unique=True)
    logo_url = models.URLField(null=True, blank=True)
    federation_level = models.CharField(
        max_length=255,
        help_text=_("The level of federation for this service."),
        choices=(
            ("auth", "Allow org authentication"),
            ("full", "Full federation"),
        ),
        default="auth",
    )
    selectable = models.BooleanField(
        default=True,
        help_text=_(
            "Whether this service can be selected by organizations for federation."
        ),
    )

    class Meta:
        verbose_name = _("Federation Support for Service")
        verbose_name_plural = _("Federation Support for Service")
        db_table = "account_federated_service"

    class HandleRef:
        tag = "federated_service"

    def __str__(self):
        return self.name


class FederatedServiceURL(HandleRefModel):
    """
    Represents a URL for a service that integrates with the organization's OAuth application.
    """

    url = models.URLField(verbose_name=_("Service URL"))
    auth = models.ForeignKey(
        AuthFederation,
        on_delete=models.CASCADE,
        related_name="federated_service_urls",
        verbose_name=_("OAuth Application"),
    )
    service = models.ForeignKey(
        ServiceFederationSupport,
        on_delete=models.CASCADE,
        related_name="urls",
        verbose_name=_("Service"),
    )
    config = models.JSONField(
        verbose_name=_("Service Configuration"),
        help_text=_("Service specific configuration for this URL."),
        default=dict,
        blank=True,
    )

    class Meta:
        verbose_name = _("Federated Service URL")
        verbose_name_plural = _("Federated Service URLs")
        unique_together = (("url", "auth"), ("service", "auth"))
        db_table = "account_federated_service_url"

    class HandleRef:
        tag = "federated_service_url"

    def __str__(self):
        return self.url

    @property
    def org(self):
        return self.auth.org


class FederatedServiceURLTag(HandleRefModel):
    """
    Represents a tag for a federated service URL. This is
    used for quick federation identification based on tags.
    """

    tag = models.CharField(max_length=255, verbose_name=_("Tag"))
    service_url = models.ForeignKey(
        FederatedServiceURL,
        on_delete=models.CASCADE,
        related_name="tags",
        verbose_name=_("Service URL"),
    )

    class Meta:
        verbose_name = _("Service URL Tag")
        verbose_name_plural = _("Service URL Tags")
        db_table = "account_federated_service_url_tag"

    class HandleRef:
        tag = "federated_service_url_tag"

    def __str__(self):
        return self.tag
