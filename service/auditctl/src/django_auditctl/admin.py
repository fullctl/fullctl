from django.contrib import admin
from django_auditctl.models.auditctl import (
    Event,
    EventTask,
    Heartbeat,
    OrganizationEmailAlert,
)

from fullctl.django.admin import BaseAdmin, BaseTabularAdmin


class EventTaskInline(BaseTabularAdmin):
    model = EventTask
    extra = 0
    readonly_fields = ["task", "task_status"]
    fields = ["task", "task_status"]

    def task_status(self, obj):
        return obj.task.status


@admin.register(Event)
class EntryAdmin(BaseAdmin):
    list_display = ("id", "object_id", "status", "org", "user", "created")
    search_fields = (
        "user__username",
        "user__email",
        "org__name",
        "org__slug",
        "object_id",
    )
    list_filter = ("status",)
    inlines = [EventTaskInline]
    autocomplete_fields = ["user"]


@admin.register(OrganizationEmailAlert)
class OrganizationEmailAlertAdmin(admin.ModelAdmin):
    list_display = ("id", "org", "email", "enabled", "threshold")
    search_fields = ("org__name", "org__slug", "email")


@admin.register(Heartbeat)
class HeartbeatAdmin(admin.ModelAdmin):
    list_display = ("id", "object_id", "updated", "interval")
    search_fields = ("object_id",)
    list_filter = ("updated",)
