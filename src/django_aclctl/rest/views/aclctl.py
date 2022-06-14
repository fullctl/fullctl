from fullctl.django.rest.core import BadRequest
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response


from fullctl.django.auditlog import auditlog
from fullctl.django.rest.api_schema import PeeringDBImportSchema
from fullctl.django.rest.core import BadRequest
from fullctl.django.rest.decorators import billable, load_object
from fullctl.django.rest.filters import CaseInsensitiveOrderingFilter
from fullctl.django.rest.mixins import CachedObjectMixin, OrgQuerysetMixin
from fullctl.django.rest.renderers import PlainTextRenderer

import django_aclctl.models as models
from django_aclctl.rest.decorators import grainy_endpoint
from django_aclctl.rest.route.aclctl import route
from django_aclctl.rest.serializers.aclctl import (
    Serializers,
)

@route
class FilterRule(CachedObjectMixin, OrgQuerysetMixin, viewsets.GenericViewSet):

    serializer_class = Serializers.filter_rule
    queryset = models.FilterRule.objects.all()
    ref_tag = "filter_rule"

    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}")
    def list(self, request, org, instance, *args, **kwargs):
        serializer = Serializers.filter_rule(
            instance = models.FilterRule.objects.filter(instance=instance),
            many = True,
        )
        return Response(serializer.data)

    @auditlog()
    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}")
    def create(self, request, org, instance, auditlog=None, *args, **kwargs):

        data = request.data
        data["instance"] = instance.id
        serializer = Serializers.filter_rule(data=data)
        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        filter_rule = serializer.save()

        return Response(Serializers.filter_rule(instance=filter_rule).data)

    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}.{filter_rule.pk}")
    def retrieve(self, request, org, filter_rule, instance, *args, **kwargs):
        serializer = Serializers.filter_rule(
            instance=filter_rule,
            many=False,
        )
        return Response(serializer.data)

    @auditlog()
    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}.{filter_rule.pk}")
    def update(self, request, org, filter_rule, instance, auditlog=None, *args, **kwargs):
        serializer = Serializers.filter_rule(
            filter_rule,
            data=request.data,
        )

        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        filter_rule = serializer.save()
        filter_rule.instance = instance
        filter_rule.save()

        return Response(Serializers.filter_rule(instance=filter_rule).data)

    @auditlog()
    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}.{filter_rule.pk}")
    def destroy(self, request, org, filter_rule, instance, auditlog=None, *args, **kwargs):
        filter_rule.delete()
        filter_rule.id = request.data.get("id")
        return Response(Serializers.filter_rule(instance=filter_rule).data)


