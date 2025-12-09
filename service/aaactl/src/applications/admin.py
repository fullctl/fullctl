from django.contrib import admin

from applications.models import Service, ServiceAPIEndpoint
from common.admin import BaseAdmin

# Register your models here.


class ServiceAPIEndpointInline(admin.TabularInline):
    model = ServiceAPIEndpoint


@admin.register(Service)
class ServiceAdmin(BaseAdmin):
    list_display = (
        "name",
        "id",
        "slug",
        "status",
        "created",
        "always_show_dashboard",
        "cross_promote",
    )
    search_fields = ("name",)
    readonly_fields = ("products_that_grant_access",)
    inlines = (ServiceAPIEndpointInline,)
    autocomplete_fields = ("org",)
