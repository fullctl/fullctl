from fullctl.django.rest.decorators import serializer_registry
from fullctl.django.rest.serializers import ModelSerializer
from fullctl.django.validators import validate_alphanumeric, validate_alphanumeric_list
from rest_framework import serializers

import django_aclctl.models as models

Serializers, register = serializer_registry()

@register
class FilterRule(ModelSerializer):

    class Meta:
        model = models.FilterRule
        fields = ["src_port", "src_prefix", "dest_port", "dest_prefix", "instance"]
