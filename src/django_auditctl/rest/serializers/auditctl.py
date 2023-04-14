try:
    from yaml import CLoader as Loader
except ImportError:
    from yaml import Loader

import fullctl.service_bridge.pdbctl as pdbctl
import yaml
from django.core.validators import RegexValidator
from django.utils.translation import ugettext_lazy as _
from django_inet.rest import IPAddressField
from fullctl.django.models.concrete.tasks import TaskLimitError
from fullctl.django.rest.decorators import serializer_registry
from fullctl.django.rest.serializers import (
    ModelSerializer,
    RequireContext,
    SoftRequiredValidator,
)
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.validators import UniqueTogetherValidator

import django_auditctl.models as models

Serializers, register = serializer_registry()

@register
class Event(ModelSerializer):

    class Meta:
        model = models.Event
        fields = [
            "id",
            "object_id",
            "data",
            "error",
            "org",
            "user",
            "status",
        ]