import fullctl.service_bridge.aaactl as aaactl
import fullctl.service_bridge.pdbctl as pdbctl
from django.conf import settings
from fullctl.django.auditlog import auditlog
from fullctl.django.rest.api_schema import PeeringDBImportSchema
from fullctl.django.rest.core import BadRequest
from fullctl.django.rest.decorators import load_object
from fullctl.django.rest.filters import CaseInsensitiveOrderingFilter
from fullctl.django.rest.mixins import CachedObjectMixin, OrgQuerysetMixin
from fullctl.django.rest.renderers import PlainTextRenderer
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

import django_auditctl.models as models
from django_auditctl.rest.decorators import grainy_endpoint
from django_auditctl.rest.route.auditctl import route
from django_auditctl.rest.serializers.auditctl import Serializers

from django_auditctl.util import parts_to_object_id


@route
class AuditEntry(CachedObjectMixin, viewsets.GenericViewSet):
    serializer_class = Serializers.audit
    queryset = models.AuditEntry.objects.all()

    @grainy_endpoint(
        namespace="audit.{request.org.permission_id}",
    )
    def list(self, request, org, instance, *args, **kwargs):
        object_id = parts_to_object_id(
            version=kwargs.get("version"),
            org_tag=kwargs.get("org_tag"),
            ref_tag=kwargs.get("ref_tag"),
            ref_id=kwargs.get("ref_id"),
        )
        queryset = self.get_queryset().filter(object_id=object_id).order_by("-created")
        serializer = Serializers.audit(queryset, many=True)
        return Response(serializer.data)


    @grainy_endpoint(
        namespace="audit.{request.org.permission_id}",
    )
    def create(self, request, org, instance, *args, **kwargs):
        object_id = parts_to_object_id(
            version=kwargs.get("version"),
            org_tag=kwargs.get("org_tag"),
            ref_tag=kwargs.get("ref_tag"),
            ref_id=kwargs.get("ref_id"),
        )
        data = request.data
        data["object_id"] = object_id
        data["user"] = request.user.id
        data["org"] = org.id
        serializer = Serializers.audit(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)