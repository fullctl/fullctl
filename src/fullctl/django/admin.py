from django.contrib import admin
from django_handleref.admin import VersionAdmin

from fullctl.django.models.concrete import OrganizationUser


class BaseAdmin(VersionAdmin):
    readonly_fields = ("version",)


class BaseTabularAdmin(admin.TabularInline):
    readonly_fields = ("version",)


class APIKeyAdmin(BaseAdmin):
    list_display = ("id", "user", "key")


class OrganizationUserInline(admin.TabularInline):
    model = OrganizationUser
    extra = 0
    fields = ("status", "user")


class OrganizationAdmin(BaseAdmin):
    list_display = ("id", "name", "slug")
    inlines = (OrganizationUserInline,)
