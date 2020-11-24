try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper

import yaml

from django.utils.translation import ugettext_lazy as _

from rest_framework import serializers

import fullctl.django.models as models

from fullctl.django.rest.decorators import serializer_registry
from fullctl.django.rest.serializers import RequireContext, ModelSerializer

Serializers, register = serializer_registry()


@register
class OrganizationUser(ModelSerializer):
    ref_tag = "orguser"

    name = serializers.SerializerMethodField()
    email = serializers.SerializerMethodField()
    you = serializers.SerializerMethodField()

    class Meta:
        model = models.OrganizationUser
        fields = ["id", "name", "email", "you"]

    def get_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}"

    def get_email(self, obj):
        return obj.user.email

    def get_you(self, obj):
        return obj.user == self.context.get("user")
