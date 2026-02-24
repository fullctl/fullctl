import json

from django.contrib import admin
from django.utils.html import format_html
from prefix_meta.models import Data, DataSubnet, Request, Response
from prefix_meta.sources.prefixmetad.models import (
    OrganizationPrefixMetaSource,
    PrefixMetaSourceConfig,
    PrefixSetPrefixMetaSource,
)
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import JsonLexer

from fullctl.django.admin import BaseAdmin


class PrefixMetaResponseInline(admin.TabularInline):
    model = Response
    extra = 0
    readonly_fields = ["pretty_data"]

    def pretty_data(self, obj):
        return format_html(
            highlight("{}", JsonLexer(), HtmlFormatter(style="colorful")),
            json.dumps(obj.data, indent=4, sort_keys=True),
        )


class DataSubnetInline(admin.TabularInline):
    model = DataSubnet
    extra = 0

    def has_change_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Request)
class PrefixMetaRequestAdmin(BaseAdmin):
    list_display = [
        "prefix",
        "source",
        "type",
        "http_status",
        "count",
        "created",
        "updated",
    ]
    list_filter = ["http_status", "source", "type"]
    inlines = [
        PrefixMetaResponseInline,
    ]
    search_fields = ["prefix__net_contained_or_equal", "prefix__net_contains_or_equals"]


@admin.register(Data)
class PrefixMetaDataAdmin(BaseAdmin):
    list_display = [
        "prefix",
        "matched_subnet_count",
        "source_name",
        "type",
        "date",
        "updated",
    ]
    list_filter = ["source_name", "date", "type"]
    search_fields = ["prefix__net_contained_or_equal", "prefix__net_contains_or_equals"]
    ordering = ["-date"]
    readonly_fields = ["pretty_data"]

    inlines = [DataSubnetInline]

    def pretty_data(self, obj):
        return format_html(
            highlight("{}", JsonLexer(), HtmlFormatter(style="colorful")),
            json.dumps(obj.data, indent=4, sort_keys=True),
        )


@admin.register(PrefixMetaSourceConfig)
class PrefixMetaSourceConfigAdmin(admin.ModelAdmin):
    list_display = ["source", "namespace"]
    list_filter = ["source", "namespace"]
    search_fields = ["source", "namespace"]


@admin.register(OrganizationPrefixMetaSource)
class OrganizationPrefixMetaSourceAdmin(admin.ModelAdmin):
    list_display = ["org", "source", "status"]
    list_filter = ["org", "source", "status"]
    search_fields = ["org__name", "source_"]
    autocomplete_fields = ("org",)


@admin.register(PrefixSetPrefixMetaSource)
class PrefixSetPrefixMetaSourceAdmin(admin.ModelAdmin):
    list_display = ["prefix_set", "source", "status"]
    list_filter = ["prefix_set", "source", "status"]
    search_fields = ["prefix_set__name", "source"]
