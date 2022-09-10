import reversion
from django.conf.urls import url
from django.contrib import admin
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django_handleref.admin import VersionAdmin

import fullctl.django.auditlog as auditlog
from fullctl.django.models.concrete import (
    AuditLog,
    Organization,
    OrganizationUser,
    Task,
    TaskSchedule,
)
from fullctl.django.models.concrete.service_bridge import ServiceBridgeAction


class BaseAdmin(VersionAdmin):
    readonly_fields = ("version",)

    def save_model(self, request, obj, form, change):
        with auditlog.Context() as ctx:
            ctx.set("user", request.user)
            ctx.set("info", "django-admin")
            with reversion.create_revision():
                return super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        with auditlog.Context() as ctx:
            ctx.set("user", request.user)
            ctx.set("info", "django-admin")
            with reversion.create_revision():
                return super().save_formset(request, form, formset, change)


class BaseTabularAdmin(admin.TabularInline):
    readonly_fields = ("version",)


class OrganizationUserInline(admin.TabularInline):
    model = OrganizationUser
    extra = 1
    fields = ("status", "user", "is_default")


@admin.register(Organization)
class OrganizationAdmin(BaseAdmin):
    list_display = ("id", "name", "slug")
    inlines = (OrganizationUserInline,)


@admin.register(Task)
class TaskAdmin(BaseAdmin):
    list_display = (
        "id",
        "source",
        "queue_id",
        "parent",
        "status",
        "op",
        "limit_id",
        "param",
        "time",
        "user",
        "org",
        "created",
        "updated",
    )
    list_filter = ("status", "op")


@admin.register(TaskSchedule)
class TaskScheduleAdmin(BaseAdmin):
    readonly_fields = BaseAdmin.readonly_fields + ("tasks",)
    list_display = (
        "id",
        "description",
        "status",
        "interval",
        "repeat",
        "user",
        "org",
        "created",
        "updated",
        "schedule",
    )


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "action",
        "object_type",
        "object_id",
        "log_object",
        "org",
        "user",
        "key",
        "info",
        "created",
    )

    readonly_fields = ("log_object",)

    search_fields = (
        "info",
        "org__name",
        "key",
        "user__username",
        "user__email",
        "object_id",
    )
    list_filter = ("action", "object_type")

    def log_object(self, obj=None):
        if obj and obj.log_object:
            return f"{obj.log_object}"
        elif obj and obj.object_id:
            return "<deleted>"
        return ""


class UrlActionMixin:
    def make_redirect(self, obj, action):
        opts = obj.model._meta
        return redirect(f"admin:{opts.app_label}_{opts.model_name}_changelist")

    def actions_view(self, request, object_id, action, **kwargs):
        """
        Allows one to call any actions defined in this model admin
        to be called via an admin view placed at <model_name>/<id>/<action>/<action_name>.
        """
        if not request.user.is_superuser:
            return HttpResponseForbidden(request)

        obj = self.get_queryset(request).filter(pk=object_id)
        if obj.exists():
            redir = self.make_redirect(obj, action)
            action = self.get_action(action)
            if action:
                action[0](self, request, obj)
                return redir
        return redirect(
            "admin:%s_%s_changelist"
            % (obj.model._meta.app_label, obj.model._meta.model_name)
        )

    def get_urls(self):
        """
        Adds the actions view as a subview of this model's admin views.
        """
        info = self.model._meta.app_label, self.model._meta.model_name

        urls = [
            url(
                r"^(\d+)/action/([\w]+)/$",
                self.admin_site.admin_view(self.actions_view),
                name="%s_%s_actions" % info,
            ),
        ] + super().get_urls()
        return urls


@admin.register(ServiceBridgeAction)
class ServiceBridgeAction(admin.ModelAdmin):
    list_display = (
        "name",
        "reference",
        "target",
        "action",
        "function",
        "description",
        "created",
        "updated",
    )
