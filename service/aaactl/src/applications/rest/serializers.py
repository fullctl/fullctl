from fullctl.django.rest.decorators import serializer_registry
from fullctl.django.rest.serializers import ModelSerializer

import applications.models as models

# from rest_framework import serializers


Serializers, register = serializer_registry()


@register
class Service(ModelSerializer):
    class Meta:
        model = models.Service
        fields = [
            "name",
            "slug",
            "api_url",
            "service_url",
            "description",
            "logo",
            "config",
        ]
