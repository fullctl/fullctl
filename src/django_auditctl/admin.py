from django.contrib import admin
from django.forms import ModelForm
from fullctl.django.admin import BaseAdmin, BaseTabularAdmin

from django_auditctl.models.auditctl import Event


@admin.register(Event)
class EntryAdmin(BaseAdmin):
    list_display = ("id", "object_id", "status", "data", "created", "org", "user")
    search_fields = (
        "user__username",
        "user__email",
        "org__name",
        "org__slug",
        "object_id",
    )
    list_filter = ("status",)
