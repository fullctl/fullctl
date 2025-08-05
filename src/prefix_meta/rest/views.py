import re
import ipaddress

from django_prefixctl.rest.decorators import grainy_endpoint
from django_prefixctl.rest.route.prefixctl import route
from django_prefixctl.models import PrefixSet
from fullctl.django.rest.core import BadRequest
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.conf import settings

import prefix_meta.models as models
from prefix_meta.rest.serializers import Serializers
from prefix_meta.sources.prefixmetad.models import (
    PrefixMetaSourceConfig,
    OrganizationPrefixMetaSource,
    PrefixSetPrefixMetaSource,
)
from prefix_meta.tasks import LocationUpdateTask


def build_sources_map():
    """
    Build a map of source patterns to their enabled status from settings
    Handles mixed naming patterns: *_ENABLED and *_CHECKS_ENABLED
    """
    sources_map = {}

    enabled_patterns = [
        re.compile(r"^(.+)_ENABLED$"),
        re.compile(r"^(.+)_CHECKS_ENABLED$"),
    ]

    for attr_name in dir(settings):
        for pattern in enabled_patterns:
            match = pattern.match(attr_name)
            if match:
                source_key = match.group(1).lower()
                sources_map[source_key] = getattr(settings, attr_name)
                break

    return sources_map


SOURCES_MAP = build_sources_map()


def get_global_default(source_name):
    """
    Determine global default status based on environment settings and source name patterns
    """
    source_name_lower = source_name.lower()

    if source_name_lower in SOURCES_MAP:
        return "ok" if SOURCES_MAP[source_name_lower] else "disabled"

    for source_key, enabled in SOURCES_MAP.items():
        if source_name_lower.startswith(source_key):
            return "ok" if enabled else "disabled"

    return "ok"


@route
class PrefixMeta(viewsets.GenericViewSet):

    """
    This is the main viewset for the prefix_meta app. It provides the following
    endpoints:

    - GET /prefix_meta/prefix/{typ}/{ip}/{mask}/: Returns all meta data for a
        given prefix. The type of meta data is specified by the `typ` parameter.
        The `ip` and `mask` parameters specify the prefix in CIDR notation.
    """

    serializer_class = Serializers.prefix_location
    queryset = models.Data.objects.all()

    ref_tag = "meta"

    @action(
        detail=False, url_path="prefix/(?P<typ>[^/]+)/(?P<ip>[^/]+)/(?P<mask>[^/]+)"
    )
    @grainy_endpoint(namespace="meta.prefix.location.{request.org.permission_id}")
    def all_by_type(self, request, org, instance, typ, ip, mask, *args, **kwargs):
        """
        Lists all meta data for a given prefix. The type of meta data is
        specified by the `typ` parameter. The `ip` and `mask` parameters specify
        the prefix in CIDR notation.
        """

        try:
            prefix = ipaddress.ip_network(f"{ip}/{mask}")
        except Exception:
            return BadRequest({"non_field_errors": ["malformed prefix"]})

        try:
            serializer_cls = getattr(Serializers, f"prefix_{typ}")
        except AttributeError:
            return BadRequest({"non_field_errors": [f"invalid meta data type: {typ}"]})

        if typ == "location":
            # TODO: modular
            if not LocationUpdateTask.last_run(f"{prefix}", age=60):
                LocationUpdateTask.create_task(f"{prefix}", user=request.user, org=org)

        qset = models.Data.objects.filter(
            prefix__net_contains_or_equals=prefix,
            type=typ,
        ).order_by("prefix")

        serializer_cls = getattr(Serializers, f"prefix_{typ}")

        serializer = serializer_cls(
            qset,
            many=True,
        )
        return Response(serializer.data)


@route
class OrganizationPrefixMetaSourceViewSet(viewsets.GenericViewSet):
    """
    ViewSet for /api/org_prefix_meta_source/{org} endpoints
    """

    serializer_class = Serializers.org_prefix_meta_source
    queryset = OrganizationPrefixMetaSource.objects.all()

    ref_tag = "org_prefix_meta_source"

    @grainy_endpoint(namespace="reputation_report.{request.org.permission_id}")
    def list(self, request, org, instance, *args, **kwargs):
        """
        GET /api/org_prefix_meta_source/{org}

        Returns consolidated representation:
        {<source_name>: {"status": <status>, "default": <default_status>}}
        """

        available_sources = PrefixMetaSourceConfig.objects.all()

        org_sources = {
            item.source.source: item.status
            for item in OrganizationPrefixMetaSource.objects.filter(org=org)
        }

        result = {}
        for source_config in available_sources:
            source_name = source_config.source

            global_default = get_global_default(source_name)

            result[source_name] = {
                "status": org_sources.get(source_name, global_default),
                "default": global_default,
            }

        serializer = self.serializer_class()
        serializer.instance = result
        return Response(serializer.data)

    @grainy_endpoint(namespace="reputation_report.{request.org.permission_id}")
    def create(self, request, org, instance, *args, **kwargs):
        """
        POST /api/org_prefix_meta_source/{org}

        Expects: {<source_name>: <status>}
        Does in-place replacement of org's OrganizationPrefixMetaSource records
        """

        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            return BadRequest(serializer.errors)

        serializer.save(org=org)

        return Response(status=status.HTTP_201_CREATED)


@route
class PrefixSetPrefixMetaSourceViewSet(viewsets.GenericViewSet):
    """
    ViewSet for /api/prefixset_prefix_meta_source/{org}/{prefix_set_id} endpoint
    """

    serializer_class = Serializers.prefixset_prefix_meta_source
    queryset = PrefixSetPrefixMetaSource.objects.all()

    ref_tag = "prefixset_prefix_meta_source"
    needs_prefix_set_id = True

    @grainy_endpoint(namespace="reputation_report.{request.org.permission_id}")
    def list(self, request, org, instance, prefix_set_id, *args, **kwargs):
        """
        GET /api/prefixset_prefix_meta_source/{org}/{prefix_set_id}

        Returns consolidated representation:
        {<source_name>: {"status": <status>, "default": <default_status>}}
        """

        if not prefix_set_id:
            return BadRequest({"non_field_errors": ["Prefix set ID required"]})

        try:
            prefix_set = PrefixSet.objects.get(id=prefix_set_id, instance__org=org)
        except PrefixSet.DoesNotExist:
            return BadRequest({"non_field_errors": ["Prefix set not found"]})

        available_sources = PrefixMetaSourceConfig.objects.all()

        prefixset_sources = {
            item.source.source: item.status
            for item in PrefixSetPrefixMetaSource.objects.filter(prefix_set=prefix_set)
        }

        org_sources = {
            item.source.source: item.status
            for item in OrganizationPrefixMetaSource.objects.filter(org=org)
        }

        result = {}
        for source_config in available_sources:
            source_name = source_config.source

            global_default = get_global_default(source_name)
            org_default = org_sources.get(source_name, global_default)

            result[source_name] = {
                "status": prefixset_sources.get(source_name, org_default),
                "default": org_default,
                "has_prefix_set_override": source_name in prefixset_sources,
            }

        serializer = self.serializer_class()
        serializer.instance = result
        return Response(serializer.data)

    @grainy_endpoint(namespace="reputation_report.{request.org.permission_id}")
    def create(self, request, org, instance, prefix_set_id, *args, **kwargs):
        """
        POST /api/prefixset_prefix_meta_source/{org}/{prefix_set_id}

        Expects: {<source_name>: <status>}
        Does in-place replacement of prefix set's PrefixSetPrefixMetaSource records
        """

        if not prefix_set_id:
            return BadRequest({"non_field_errors": ["Prefix set ID required"]})

        try:
            prefix_set = PrefixSet.objects.get(id=prefix_set_id, instance__org=org)
        except PrefixSet.DoesNotExist:
            return BadRequest({"non_field_errors": ["Prefix set not found"]})

        data = request.data.copy()
        data['prefix_set_id'] = prefix_set_id

        serializer = self.serializer_class(data=data)
        if not serializer.is_valid():
            return BadRequest(serializer.errors)

        serializer.save(prefix_set=prefix_set)

        return Response(status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["DELETE"])
    @grainy_endpoint(namespace="reputation_report.{request.org.permission_id}")
    def reset_to_defaults(self, request, org, instance, prefix_set_id, *args, **kwargs):
        """
        DELETE /api/prefixset_prefix_meta_source/{org}/{prefix_set_id}/reset_to_defaults

        Removes all prefix-set level source configurations, causing the prefix set
        to fall back to organization-level defaults.
        """

        if not prefix_set_id:
            return BadRequest({"non_field_errors": ["Prefix set ID required"]})

        try:
            prefix_set = PrefixSet.objects.get(id=prefix_set_id, instance__org=org)
        except PrefixSet.DoesNotExist:
            return BadRequest({"non_field_errors": ["Prefix set not found"]})

        # Delete all prefix-set level source configurations
        deleted_count, _ = PrefixSetPrefixMetaSource.objects.filter(
            prefix_set=prefix_set
        ).delete()

        return Response({
            "message": f"Removed {deleted_count} custom source configurations. Prefix set will now use organization defaults.",
            "deleted_count": deleted_count
        }, status=status.HTTP_200_OK)
