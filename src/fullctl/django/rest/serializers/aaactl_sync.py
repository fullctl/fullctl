from django.contrib.auth import get_user_model
from rest_framework import serializers

from fullctl.django.rest.decorators import serializer_registry

import fullctl.django.models as models

Serializers, register = serializer_registry()


@register
class User(serializers.ModelSerializer):

    ref_tag = "user"

    class Meta:
        model = get_user_model()
        fields = ["username", "first_name", "last_name", "email"]

@register
class Organization(serializers.ModelSerializer):

    class Meta:
        model = models.Organization
        fields = ["name", "slug"]


@register
class OrganizationUser(serializers.ModelSerializer):

    class Meta:
        model = models.OrganizationUser
        fields = ["org", "user"]

@register
class ExpireSession(serializers.Serializer):

    username = serializers.CharField()

    ref_tag = "expire_session"

    class Meta:
        fields = ["username"]


