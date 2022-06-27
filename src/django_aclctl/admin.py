
from django.contrib import admin

from fullctl.django.admin import BaseAdmin, BaseTabularAdmin
from fullctl.django.models.concrete import OrganizationUser

from django_aclctl.models import (
	FilterRule,
	FilterRuleTemplate,
)

@admin.register(FilterRule)
class FilterRuleAdmin(BaseAdmin):

    list_display = ("instance", "org", "src_port", "src_prefix", "src_prefix_set", "dest_port", "dest_prefix", "created", "updated")
    readonly_fields = ("org", "src_prefix_set_object")

    search_fields = ("instance__org__name", "instance__org__slug", "src_prefix", "dest_prefix")

    def org(self, obj):
        return obj.instance.org

    def src_prefix_set_object(self, obj):
        if not obj.src_prefix_set:
            return "?"
        ref_obj = obj.src_prefix_set.object
        return f"{ref_obj.name} ({obj.src_prefix_set.source})"


@admin.register(FilterRuleTemplate)
class FilterRuleTemplateAdmin(BaseAdmin):

    list_display= ["instance", "org", "name", "type", "created", "updated"]

    def org(self, obj):
        return obj.instance.org
