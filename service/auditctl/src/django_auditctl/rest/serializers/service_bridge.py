import django_auditctl.models.auditctl as models
from rest_framework import serializers

from fullctl.django.rest.decorators import serializer_registry
from fullctl.django.rest.serializers import ModelSerializer

Serializers, register = serializer_registry()


@register
class Event(ModelSerializer):
    status = serializers.CharField(help_text="Event status", default="ok")

    ref_tag = "event"

    class Meta:
        model = models.Event
        fields = [
            "id",
            "object_id",
            "org",
            "source",
            "data",
            "error",
            "status",
        ]
