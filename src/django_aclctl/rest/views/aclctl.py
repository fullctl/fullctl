import os

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
from fullctl.django.rest.views.template import TemplateRenderView

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

        queryset = models.FilterRule.objects.filter(instance=instance).order_by("priority")
        serializer = Serializers.filter_rule(
            instance = queryset,
            many = True,
        )
        return Response(serializer.data)

    @auditlog()
    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}")
    def create(self, request, org, instance, auditlog=None, *args, **kwargs):

        data = request.data
        data["instance"] = instance.id

        if data.get("priority", "") == "":
            data["priority"] = models.FilterRule.new_rule_priority(instance)

        serializer = Serializers.filter_rule(data=data)
        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        filter_rule = serializer.save()

        return Response(Serializers.filter_rule(instance=filter_rule).data)

    @load_object("filter_rule", models.FilterRule, pk="pk", instance="instance")
    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}.{filter_rule.pk}")
    def retrieve(self, request, org, filter_rule, instance, *args, **kwargs):
        serializer = Serializers.filter_rule(
            instance=filter_rule,
            many=False,
        )
        return Response(serializer.data)

    @load_object("filter_rule", models.FilterRule, pk="pk", instance="instance")
    @auditlog()
    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}.{filter_rule.pk}")
    def update(self, request, org, filter_rule, instance, auditlog=None, *args, **kwargs):

        data = request.data
        data["instance"] = instance.id

        serializer = Serializers.filter_rule(
            filter_rule,
            data=data,
        )

        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        filter_rule = serializer.save()
        filter_rule.save()

        return Response(Serializers.filter_rule(instance=filter_rule).data)

    @load_object("filter_rule", models.FilterRule, pk="pk", instance="instance")
    @auditlog()
    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}.{filter_rule.pk}")
    def destroy(self, request, org, filter_rule, instance, auditlog=None, *args, **kwargs):
        filter_rule.delete()
        filter_rule.id = request.data.get("id")
        return Response(Serializers.filter_rule(instance=filter_rule).data)

@route
class FilterRuleTemplate(CachedObjectMixin, OrgQuerysetMixin, viewsets.GenericViewSet):
    serializer_class = Serializers.filter_rule_template
    queryset = models.FilterRuleTemplate.objects.all()


    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}")
    def list(self, request, org, instance, *args, **kwargs):
        queryset = models.FilterRuleTemplate.objects.filter(instance=instance)
        serializer = self.serializer_class(
            instance = queryset,
            many = True,
        )
        return Response(serializer.data)

    @auditlog()
    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}")
    def create(self, request, org, instance, auditlog=None, *args, **kwargs):

        data = request.data
        data["instance"] = instance.id

        serializer = self.serializer_class(data=data)
        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        tmpl = serializer.save()

        return Response(Serializers.filter_rule_template(instance=tmpl).data)

    @load_object("tmpl", models.FilterRuleTemplate, pk="pk", instance="instance")
    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}.{tmpl.pk}")
    def retrieve(self, request, org, tmpl, instance, *args, **kwargs):
        serializer = self.serializer_class(
            instance=tmpl,
            many=False,
        )
        return Response(serializer.data)

    @load_object("tmpl", models.FilterRuleTemplate, pk="pk", instance="instance")
    @auditlog()
    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}.{tmpl.pk}")
    def update(self, request, org, tmpl, instance, auditlog=None, *args, **kwargs):

        data = request.data
        data["instance"] = instance.id

        serializer = self.serializer_class(
            tmpl,
            data=data,
        )

        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        tmpl = serializer.save()
        ftmpl.save()

        return Response(self.serializer_class(instance=tmpl).data)

    @load_object("tmpl", models.FilterRuleTemplate, pk="pk", instance="instance")
    @auditlog()
    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}.{tmpl.pk}")
    def destroy(self, request, org, tmpl, instance, auditlog=None, *args, **kwargs):
        tmpl.delete()
        tmpl.id = request.data.get("id")
        return Response(self.serializer_class(instance=tmpl).data)





@route
class FilterRuleConfig(TemplateRenderView):
    serializer_class = Serializers.filter_rule_config
    queryset = models.FilterRuleTemplate.objects.all()
    ref_tag = "config"


    @action(detail=False, methods=["post", "get"], url_name="filter_rule_config", url_path="filter_rules/(?P<type>[^/.]+)/(?P<tmpl_id>[^/.]+)")
    @auditlog()
    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}.render")
    def render(self, request, org, instance, type, tmpl_id, auditlog=None, *args, **kwargs):
        return Response(self._render(request, instance, type, tmpl_id, *args, **kwargs).data)

    @action(detail=False, methods=["post", "get"], renderer_classes=[PlainTextRenderer], url_name="filter_rule_config", url_path="filter_rules/(?P<type>[^/.]+)/(?P<tmpl_id>[^/.]+)/plain")
    @auditlog()
    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}.render")
    def render_plain(self, request, org, instance, type, tmpl_id, auditlog=None, *args, **kwargs):
        serializer = self._render(request, instance, type, tmpl_id, *args, **kwargs)
        return Response(serializer.data["body"])
