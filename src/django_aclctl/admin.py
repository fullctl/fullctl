from django.contrib import admin
from fullctl.django.admin import BaseAdmin

from django_aclctl.models import AccessControlList, FilterRule, FilterRuleTemplate


class FilterRuleInlineAdmin(admin.TabularInline):
    model = FilterRule


@admin.register(AccessControlList)
class AccessControlListAdmin(BaseAdmin):
    list_display = ("instance", "org", "name", "created", "updated")
    readonly_fields = ("org",)
    inlines = (FilterRuleInlineAdmin,)

    def org(self, obj):
        return obj.instance.org


@admin.register(FilterRule)
class FilterRuleAdmin(BaseAdmin):
    list_display = (
        "access_control_list",
        "org",
        "src_port",
        "src_prefix",
        "src_prefix_set",
        "dest_port",
        "dest_prefix",
        "dest_prefix_set",
        "created",
        "updated",
    )
    readonly_fields = ("org", "src_prefix_set_object", "dest_prefix_set_object")

    search_fields = (
        "access_control_list__instance__org__name",
        "access_control_list__instance__org__slug",
        "access_control_list__name",
        "src_prefix",
        "dest_prefix",
    )

    def org(self, obj):
        return obj.instance.org

    def src_prefix_set_object(self, obj):
        if not obj.src_prefix_set:
            return "?"
        ref_obj = obj.src_prefix_set.object
        return f"{ref_obj.name} ({obj.src_prefix_set.source})"

    def dest_prefix_set_object(self, obj):
        if not obj.dest_prefix_set:
            return "?"
        ref_obj = obj.dest_prefix_set.object
        return f"{ref_obj.name} ({obj.dest_prefix_set.source})"


@admin.register(FilterRuleTemplate)
class FilterRuleTemplateAdmin(BaseAdmin):
    list_display = ["instance", "org", "name", "type", "created", "updated"]

    def org(self, obj):
        return obj.instance.org
