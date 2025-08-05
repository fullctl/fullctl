import ipaddress

from fullctl.django.rest.decorators import serializer_registry

# from fullctl.django.rest.serializers import ModelSerializer
from fullctl.django.rest.serializers.meta import Data
from rest_framework import serializers
from prefix_meta.sources.prefixmetad.models import (
    PrefixMetaSourceConfig,
    OrganizationPrefixMetaSource,
    PrefixSetPrefixMetaSource,
)

import prefix_meta.models as models

Serializers, register = serializer_registry()


@register
class RequestLocation(serializers.Serializer):
    """
    Serializer for triggering a location request for a prefix.
    """

    ref_tag = "request_prefix_location"
    prefixes = serializers.JSONField()

    def validate_prefixes(self, prefixes):
        for prefix in prefixes:
            ipaddress.ip_network(prefix)
        return prefixes


@register
class Location(Data):
    """
    Serializer for location data.
    """

    ref_tag = "prefix_location"

    country_code = serializers.SerializerMethodField()
    city = serializers.SerializerMethodField()
    region = serializers.SerializerMethodField()
    geo = serializers.SerializerMethodField()
    isp = serializers.SerializerMethodField()

    class Meta(Data.Meta):
        model = models.Data
        fields = [
            "prefix",
            "id",
            "country_code",
            "region",
            "city",
            "geo",
            "isp",
            "data",
        ]

    def get_country_code(self, obj):
        return self.meta_data(obj, "country_code")

    def get_city(self, obj):
        return self.meta_data(obj, "city_name")

    def get_region(self, obj):
        return self.meta_data(obj, "region_name")

    def get_geo(self, obj):
        return {
            "latitude": self.meta_data(obj, "latitude"),
            "longitude": self.meta_data(obj, "longitude"),
        }

    def get_isp(self, obj):
        return self.meta_data(obj, "isp")


@register
class PrefixMetaSourceConfigSerializer(serializers.Serializer):
    """
    Serializer for PrefixMetaSourceConfig model.
    """

    ref_tag = "prefix_meta_source_config"

    class Meta:
        model = PrefixMetaSourceConfig
        fields = ["source", "namespace"]


@register
class OrganizationPrefixMetaSourceSerializer(serializers.Serializer):
    """
    Serializer for OrganizationPrefixMetaSource model.
    """

    ref_tag = "org_prefix_meta_source"

    class Meta:
        model = OrganizationPrefixMetaSource
        fields = ["org", "source", "status"]

    def to_internal_value(self, data):
        """Override to handle dynamic dictionary input"""
        return data

    def validate(self, data):
        """
        Validate dictionary input: {<source_name>: <status>}
        All source names exist in PrefixMetaSourceConfig
        and status is one of ["ok", "disabled"].
        """
        if not isinstance(data, dict):
            raise serializers.ValidationError("Expected dictionary format")

        valid_statuses = ["ok", "disabled"]
        for source_name, source_status in data.items():
            if not PrefixMetaSourceConfig.objects.filter(source=source_name).exists():
                raise serializers.ValidationError(
                    f"Source '{source_name}' does not exist"
                )
            if source_status not in valid_statuses:
                raise serializers.ValidationError(
                    f"Invalid status '{source_status}' for source '{source_name}'"
                )

        return data

    def to_representation(self, instance):
        if isinstance(instance, dict):
            return instance
        return super().to_representation(instance)

    def save(self, org):
        """
        Handle the creation/deletion for OrganizationPrefixMetaSource records.
        Does in-place replacement of org's OrganizationPrefixMetaSource records.
        """
        data = self.validated_data

        # Delete existing entries not in the new data
        sources_to_keep = set(data.keys())
        OrganizationPrefixMetaSource.objects.filter(org=org).exclude(
            source__source__in=sources_to_keep
        ).delete()

        # Update or create entries from the new data
        for source_name, source_status in data.items():
            source_config = PrefixMetaSourceConfig.objects.get(source=source_name)

            OrganizationPrefixMetaSource.objects.update_or_create(
                org=org, source=source_config, defaults={"status": source_status}
            )


@register
class PrefixSetPrefixMetaSourceSerializer(serializers.Serializer):
    """
    Serializer for PrefixSetPrefixMetaSource model.
    """

    ref_tag = "prefixset_prefix_meta_source"

    class Meta:
        model = PrefixSetPrefixMetaSource
        fields = ["prefix_set", "source", "status"]

    def to_internal_value(self, data):
        """Override to handle dynamic dictionary input"""
        if 'prefix_set_id' not in data:
            raise serializers.ValidationError("prefix_set_id is required")

        self.prefix_set_id = data.pop('prefix_set_id')

        return data

    def validate(self, data):
        """
        Validate dictionary input: {<source_name>: <status>}
        All source names exist in PrefixMetaSourceConfig
        and status is one of ["ok", "disabled"].
        """
        if not isinstance(data, dict):
            raise serializers.ValidationError("Expected dictionary format")

        if not hasattr(self, "prefix_set_id") or not self.prefix_set_id:
            raise serializers.ValidationError("prefix_set_id is required")

        valid_statuses = ["ok", "disabled"]
        for source_name, source_status in data.items():
            if not PrefixMetaSourceConfig.objects.filter(source=source_name).exists():
                raise serializers.ValidationError(
                    f"Source '{source_name}' does not exist"
                )
            if source_status not in valid_statuses:
                raise serializers.ValidationError(
                    f"Invalid status '{source_status}' for source '{source_name}'"
                )
        return data

    def to_representation(self, instance):
        if isinstance(instance, dict):
            return instance
        return super().to_representation(instance)

    def save(self, prefix_set):
        """
        Handle the creation/deletion for PrefixSetPrefixMetaSource records.
        Does in-place replacement of prefix set's PrefixSetPrefixMetaSource records.
        """
        data = self.validated_data

        # Delete existing entries not in the new data
        sources_to_keep = set(data.keys())
        PrefixSetPrefixMetaSource.objects.filter(prefix_set=prefix_set).exclude(
            source__source__in=sources_to_keep
        ).delete()

        # Update or create entries from the new data
        for source_name, source_status in data.items():
            source_config = PrefixMetaSourceConfig.objects.get(source=source_name)

            PrefixSetPrefixMetaSource.objects.update_or_create(
                prefix_set=prefix_set,
                source=source_config,
                defaults={"status": source_status},
            )
