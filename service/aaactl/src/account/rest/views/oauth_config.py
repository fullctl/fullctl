from secrets import token_urlsafe

import account.models as models
from account.rest.route import route
from account.rest.serializers import Serializers
from common.rest.decorators import grainy_endpoint
from rest_framework import viewsets
from rest_framework.response import Response

from fullctl.django.auditlog import auditlog


@route
class OAuthConfig(viewsets.ViewSet):
    """
    Rotates the OAuth client secret for an existing OAuthConfig.

    The OAuthConfig itself (key, URLs, scopes) is managed via Django admin;
    this endpoint exists solely so the secret can be rotated programmatically
    via an API key. Authorized by ``oauth_config.{service_id}`` permission.

    PUT /api/account/oauth_config/{service_id}/  body: {"secret": "..."} (optional)

    If ``secret`` is provided it replaces the stored value. If ``secret`` is
    omitted, a random value is generated locally; this is only useful for
    "invalidate then reset" flows where the OAuth provider's stored secret
    is updated out of band — otherwise the next OAuth login will fail until
    the provider's value is brought back in sync. The new secret is returned
    in the response.
    """

    serializer_class = Serializers.oauth_config
    queryset = models.OAuthConfig.objects.all()
    lookup_field = "service_id"
    lookup_value_regex = r"[a-z0-9_]+"

    @auditlog()
    @grainy_endpoint("oauth_config.{service_id}")
    def update(self, request, service_id, *args, auditlog=None, **kwargs):
        try:
            config = models.OAuthConfig.objects.get(service_id=service_id)
        except models.OAuthConfig.DoesNotExist:
            return Response(status=404)

        serializer = Serializers.oauth_config(
            instance=config, data=request.data, partial=True
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        provided_secret = serializer.validated_data.get("secret")
        config.secret = provided_secret or token_urlsafe()
        # Only touch the secret-related columns so a concurrent admin edit of
        # key/URLs/scopes isn't silently overwritten by stale instance values.
        config.save(update_fields=["secret", "updated"])

        if auditlog is not None:
            auditlog.log(
                "oauth_config_rotate_secret",
                log_object=config,
                service_id=service_id,
                generated=not bool(provided_secret),
            )

        return Response(Serializers.oauth_config(instance=config).data)
