from django.contrib import admin

from .models import OrganizationBranding


@admin.register(OrganizationBranding)
class OrganizationBrandingAdmin(admin.ModelAdmin):
    list_display = ("org",)
    search_fields = ("org__name",)
