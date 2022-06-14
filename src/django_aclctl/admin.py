
from django.contrib import admin

from fullctl.django.admin import BaseAdmin, BaseTabularAdmin
from fullctl.django.models.concrete import OrganizationUser

from django_aclctl.models import (
	FilterRule,
)

@admin.register(FilterRule)
class FilterRuleAdmin(BaseAdmin):

    list_display = ("instance", "org", "src_port", "src_prefix", "dest_port", "dest_prefix", "created", "updated")
    readonly_fields = ("org", )

    search_fields = ("instance__org__name", "instance__org__slug", "src_prefix", "dest_prefix")

    def org(self, obj):
        return obj.instance.org
