import account.models as models
from account.rest.serializers import register
from rest_framework import serializers


@register
class OAuthConfig(serializers.ModelSerializer):
    """
    Serializer for the secret-rotation endpoint.

    ``secret`` is the only writable field — ``service_id`` and ``key`` are
    read-only since the underlying record is administered through Django
    admin. The rotation endpoint deliberately exposes ``secret`` in the
    response so the caller can capture the newly generated value.
    """

    secret = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = models.OAuthConfig
        fields = ["service_id", "key", "secret"]
        read_only_fields = ["service_id", "key"]
