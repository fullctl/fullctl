from fullctl.django.auditlog import auditlog
from fullctl.django.rest.core import BadRequest
from fullctl.django.rest.decorators import load_object
from fullctl.django.rest.mixins import CachedObjectMixin, OrgQuerysetMixin
from fullctl.django.rest.renderers import PlainTextRenderer
from fullctl.django.rest.views.template import TemplateRenderView
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

import django_aclctl.models as models
from django_aclctl.rest.decorators import grainy_endpoint
from django_aclctl.rest.route.aclctl import route
from django_aclctl.rest.serializers.aclctl import Serializers


@route
class AccessControlList(CachedObjectMixin, OrgQuerysetMixin, viewsets.GenericViewSet):

    serializer_class = Serializers.access_control_list
    queryset = models.AccessControlList.objects.all()
    ref_tag = "access_control_list"
    lookup_url_kwarg = "acl_tag"
    lookup_field = "slug"

    @grainy_endpoint(namespace="access_control_list.{request.org.permission_id}")
    def list(self, request, org, instance, *args, **kwargs):

        queryset = models.AccessControlList.objects.filter(instance=instance).order_by(
            "name"
        )
        serializer = Serializers.access_control_list(
            instance=queryset,
            many=True,
        )
        return Response(serializer.data)

    @auditlog()
    @grainy_endpoint(namespace="access_control_list.{request.org.permission_id}")
    def create(self, request, org, instance, auditlog=None, *args, **kwargs):
        data = request.data
        data["instance"] = instance.id
        serializer = Serializers.access_control_list(data=data)
        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        access_control_list = serializer.save()

        return Response(
            Serializers.access_control_list(instance=access_control_list).data
        )

    @load_object(
        "access_control_list",
        models.AccessControlList,
        slug="acl_tag",
        instance="instance",
    )
    @grainy_endpoint(
        namespace="access_control_list.{request.org.permission_id}.{access_control_list.pk}"
    )
    def retrieve(self, request, org, access_control_list, instance, *args, **kwargs):
        serializer = Serializers.access_control_list(
            instance=access_control_list,
            many=False,
        )
        return Response(serializer.data)

    @load_object(
        "access_control_list",
        models.AccessControlList,
        slug="acl_tag",
        instance="instance",
    )
    @auditlog()
    @grainy_endpoint(
        namespace="access_control_list.{request.org.permission_id}.{access_control_list.pk}"
    )
    def update(
        self,
        request,
        org,
        access_control_list,
        instance,
        auditlog=None,
        *args,
        **kwargs
    ):

        data = request.data
        data["instance"] = instance.id

        serializer = Serializers.access_control_list(
            access_control_list,
            data=data,
        )

        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        access_control_list = serializer.save()
        return Response(
            Serializers.access_control_list(instance=access_control_list).data
        )

    @load_object(
        "access_control_list",
        models.AccessControlList,
        slug="acl_tag",
        instance="instance",
    )
    @auditlog()
    @grainy_endpoint(
        namespace="access_control_list.{request.org.permission_id}.{access_control_list.pk}"
    )
    def destroy(
        self,
        request,
        org,
        access_control_list,
        instance,
        auditlog=None,
        *args,
        **kwargs
    ):
        access_control_list.delete()
        access_control_list.id = request.data.get("id")
        return Response(
            Serializers.access_control_list(instance=access_control_list).data
        )

    @action(detail=True, methods=["GET"])
    @load_object(
        "access_control_list",
        models.AccessControlList,
        slug="acl_tag",
        instance="instance",
    )
    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}")
    def filter_rules(
        self, request, org, instance, access_control_list, *args, **kwargs
    ):
        queryset = models.FilterRule.objects.filter(
            access_control_list=access_control_list
        ).order_by("priority")
        serializer = Serializers.filter_rule(
            instance=queryset,
            many=True,
        )
        return Response(serializer.data)


@route
class FilterRule(CachedObjectMixin, viewsets.GenericViewSet):

    serializer_class = Serializers.filter_rule
    queryset = models.FilterRule.objects.all()
    ref_tag = "filter_rule"

    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}")
    def list(self, request, org, instance, *args, **kwargs):

        queryset = models.FilterRule.objects.filter(
            access_control_list__instance=instance
        )

        if request.GET.get("access_control_list"):
            access_control_list = models.AccessControlList.objects.get(
                id=request.GET["access_control_list"]
            )
            queryset = queryset.filter(access_control_list=access_control_list)

        queryset = queryset.order_by("priority")

        serializer = Serializers.filter_rule(
            instance=queryset,
            many=True,
        )
        return Response(serializer.data)

    @auditlog()
    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}")
    def create(self, request, org, instance, auditlog=None, *args, **kwargs):

        data = request.data

        access_control_list = models.AccessControlList.objects.get(
            id=data["access_control_list"]
        )

        if data.get("priority", "") == "":
            data["priority"] = models.FilterRule.new_rule_priority(access_control_list)

        serializer = Serializers.filter_rule(data=data)
        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        filter_rule = serializer.save()

        return Response(Serializers.filter_rule(instance=filter_rule).data)

    @load_object(
        "filter_rule",
        models.FilterRule,
        pk="pk",
        access_control_list__instance="instance",
    )
    @grainy_endpoint(
        namespace="filter_rule.{request.org.permission_id}.{filter_rule.pk}"
    )
    def retrieve(self, request, org, filter_rule, instance, *args, **kwargs):
        serializer = Serializers.filter_rule(
            instance=filter_rule,
            many=False,
        )
        return Response(serializer.data)

    @load_object(
        "filter_rule",
        models.FilterRule,
        pk="pk",
        access_control_list__instance="instance",
    )
    @auditlog()
    @grainy_endpoint(
        namespace="filter_rule.{request.org.permission_id}.{filter_rule.pk}"
    )
    def update(
        self, request, org, filter_rule, instance, auditlog=None, *args, **kwargs
    ):

        data = request.data
        serializer = Serializers.filter_rule(
            filter_rule,
            data=data,
        )

        if not serializer.is_valid():
            return BadRequest(serializer.errors)
        filter_rule = serializer.save()
        filter_rule.save()

        return Response(Serializers.filter_rule(instance=filter_rule).data)

    @load_object(
        "filter_rule",
        models.FilterRule,
        pk="pk",
        access_control_list__instance="instance",
    )
    @auditlog()
    @grainy_endpoint(
        namespace="filter_rule.{request.org.permission_id}.{filter_rule.pk}"
    )
    def destroy(
        self, request, org, filter_rule, instance, auditlog=None, *args, **kwargs
    ):
        response = Response(Serializers.filter_rule(instance=filter_rule).data)
        filter_rule.delete()
        return response


@route
class FilterRuleTemplate(CachedObjectMixin, OrgQuerysetMixin, viewsets.GenericViewSet):
    serializer_class = Serializers.filter_rule_template
    queryset = models.FilterRuleTemplate.objects.all()
    ref_tag = "filter_rule_template"

    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}")
    def list(self, request, org, instance, *args, **kwargs):
        queryset = models.FilterRuleTemplate.objects.filter(instance=instance)

        filter_type = request.GET.get("type")
        if filter_type:
            queryset = queryset.filter(type=filter_type)

        serializer = self.serializer_class(
            instance=queryset,
            many=True,
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
        tmpl.save()

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

    @action(
        detail=False,
        methods=["post", "get"],
        url_name="filter-rule",
        url_path="filter_rules/(?P<acl_tag>[^/.]+)/(?P<type>[^/.]+)/(?P<tmpl_id>[^/.]+)",
    )
    @auditlog()
    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}.render")
    def render(
        self,
        request,
        org,
        instance,
        acl_tag,
        type,
        tmpl_id,
        auditlog=None,
        *args,
        **kwargs
    ):
        access_control_list = models.AccessControlList.objects.get(
            instance=instance, slug=acl_tag
        )
        return Response(
            self._render(
                request,
                instance,
                type,
                tmpl_id,
                context={"access_control_list": access_control_list},
                *args,
                **kwargs
            ).data
        )

    @action(
        detail=False,
        methods=["post", "get"],
        renderer_classes=[PlainTextRenderer],
        url_name="filter-rule-plain",
        url_path="filter_rules/(?P<acl_tag>[^/.]+)/(?P<type>[^/.]+)/(?P<tmpl_id>[^/.]+)/plain",
    )
    @auditlog()
    @grainy_endpoint(namespace="filter_rule.{request.org.permission_id}.render")
    def render_plain(
        self,
        request,
        org,
        instance,
        acl_tag,
        type,
        tmpl_id,
        auditlog=None,
        *args,
        **kwargs
    ):
        access_control_list = models.AccessControlList.objects.get(
            instance=instance, slug=acl_tag
        )
        serializer = self._render(
            request,
            instance,
            type,
            tmpl_id,
            context={"access_control_list": access_control_list},
            *args,
            **kwargs
        )
        return Response(serializer.data["body"])
