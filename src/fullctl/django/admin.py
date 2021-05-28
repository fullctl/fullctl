from django.contrib import admin
from django_handleref.admin import VersionAdmin

from fullctl.django.models.concrete import OrganizationUser, AuditLog

class BaseAdmin(VersionAdmin):
    readonly_fields = ("version",)


class BaseTabularAdmin(admin.TabularInline):
    readonly_fields = ("version",)


class OrganizationUserInline(admin.TabularInline):
    model = OrganizationUser
    extra = 0
    fields = ("status", "user")


class OrganizationAdmin(BaseAdmin):
    list_display = ("id", "name", "slug")
    inlines = (OrganizationUserInline,)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "log_object", "user", "user_key", "org_key", "info", "created")
