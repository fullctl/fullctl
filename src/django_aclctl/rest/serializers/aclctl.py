from fullctl.django.rest.decorators import serializer_registry
from fullctl.django.rest.serializers import ModelSerializer
from fullctl.django.validators import validate_alphanumeric, validate_alphanumeric_list
from rest_framework import serializers

import django_aclctl.models as models

Serializers, register = serializer_registry()

@register
class FilterRule(ModelSerializer):

    src_prefix_set_name = serializers.SerializerMethodField()

    class Meta:
        model = models.FilterRule
        fields = ["src_type", "src_port", "src_prefix", "src_prefix_set", "src_prefix_set_name", "dest_port", "dest_prefix", "instance"]


    def get_src_prefix_set_name(self, obj):

        if not obj.src_prefix_set or not hasattr(obj.src_prefix_set, "object"):
            return None

        return obj.src_prefix_set.object.name;
