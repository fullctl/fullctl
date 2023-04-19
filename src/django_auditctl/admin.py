from django.contrib import admin
from django.forms import ModelForm
from fullctl.django.admin import BaseAdmin, BaseTabularAdmin

from django_auditctl.models.auditctl import Event, EventTask

class EventTaskInline(BaseTabularAdmin):
    model = EventTask
    extra = 0
    readonly_fields = ["task", "task_status"]
    fields = ["task", "task_status"]

    def task_status(self, obj):
        return obj.task.status

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
    inlines = [EventTaskInline]
