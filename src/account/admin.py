import reversion
from django import forms
from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils.safestring import mark_safe
from django_grainy.admin import GrainyUserAdmin
from django_grainy.forms import (
    PERM_CHOICES_FOR_FIELD,
    BitmaskSelect,
    PermissionFormField,
    UserPermissionForm,
)
from fullctl.django.admin import BaseAdmin, UrlActionMixin
from fullctl.django.context import current_request

from account.impersonate import (
    is_impersonating,
    start_impersonation,
    stop_impersonation,
)
from account.models import (
    APIKey,
    APIKeyPermission,
    ContactMessage,
    EmailConfirmation,
    InternalAPIKey,
    InternalAPIKeyPermission,
    Invitation,
    ManagedPermission,
    ManagedPermissionRoleAutoGrant,
    Organization,
    OrganizationAPIKey,
    OrganizationAPIKeyPermission,
    OrganizationManagedPermission,
    OrganizationRole,
    OrganizationUser,
    PasswordReset,
    Role,
    UserPermissionOverride,
    UserSettings,
)
from account.models.federation import (
    AuthFederation,
    FederatedServiceURL,
    ServiceFederationSupport,
    FederatedServiceURLTag,
)

# registered models


@admin.register(UserPermissionOverride)
class UserPermissionOverrideAdmin(BaseAdmin):
    list_display = ("user", "org", "namespace", "permissions", "created", "updated")
    search_fields = (
        "user__username",
        "user__email",
        "org__name",
        "org__slug",
    )
    autocomplete_fields = ("user", "org")


@admin.register(Role)
class RoleAdmin(BaseAdmin):
    list_display = (
        "name",
        "description",
        "level",
        "auto_set_on_creator",
        "auto_set_on_member",
        "created",
        "updated",
    )
    ordering = ("level",)


@admin.register(UserSettings)
class UserSettingsAdmin(admin.ModelAdmin):
    list_display = ("user", "email_confirmed")
    autocomplete_fields = ("user",)


class InlineAPIKeyPermission(admin.TabularInline):
    model = APIKeyPermission
    extra = 1
    form = UserPermissionForm


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ("key", "user", "name", "managed", "readonly", "created")
    search_fields = ("name", "user__username", "user__email", "key")
    inlines = (InlineAPIKeyPermission,)


class InlineInternalAPIKeyPermission(admin.TabularInline):
    model = InternalAPIKeyPermission
    extra = 1
    form = UserPermissionForm


@admin.register(InternalAPIKey)
class InternalAPIKeyAdmin(admin.ModelAdmin):
    list_display = ("key", "name", "created")
    search_fields = ("name", "key")
    inlines = (InlineInternalAPIKeyPermission,)


class InlineOrganizationAPIKeyPermission(admin.TabularInline):
    model = OrganizationAPIKeyPermission
    extra = 1
    form = UserPermissionForm


@admin.register(OrganizationAPIKey)
class OrganizationAPIKeyAdmin(admin.ModelAdmin):
    list_display = ("key", "org", "name", "managed", "created")
    search_fields = ("org__name", "org__slug", "email", "key")
    inlines = (InlineOrganizationAPIKeyPermission,)
    autocomplete_fields = ("org",)


class OrganizationUserInline(admin.TabularInline):
    model = OrganizationUser
    extra = 1
    fields = ("user", "is_default")
    autocomplete_fields = ("user",)


class OrganizationRoleInline(admin.TabularInline):
    model = OrganizationRole
    extra = 1
    fields = ("user", "role")
    autocomplete_fields = ("user",)

    def get_formset(self, request, obj=None, **kwargs):
        formset = super().get_formset(request, obj=obj, **kwargs)
        if obj:
            formset.form.base_fields["user"].queryset = get_user_model().objects.filter(
                org_user_set__org=obj
            )
        return formset


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "slug")
    search_fields = ("name", "slug", "user__username")
    ordering = ("-user", "name")

    def get_inlines(self, request, obj=None):
        if obj is not None:
            return [OrganizationUserInline, OrganizationRoleInline]
        return [OrganizationUserInline]

    @reversion.create_revision()
    def save_formset(self, request, form, formset, change):
        return super().save_formset(request, form, formset, change)

    # dont allow deletion

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Invitation)
class InvitationAdmin(admin.ModelAdmin):
    list_display = ("org", "email", "created_by", "created", "status", "role", "expiry")
    readonly_fields = GrainyUserAdmin.readonly_fields + ("expiry",)
    search_fields = ("org__name", "org__slug", "email")


@admin.register(EmailConfirmation)
class EmailConfirmationAdmin(admin.ModelAdmin):
    list_display = ("user", "email", "created", "updated", "status")
    search_fields = ("user__username", "user__last_name", "email")


@admin.register(PasswordReset)
class PasswordResetAdmin(admin.ModelAdmin):
    list_display = ("user", "email", "created", "updated", "status")
    search_fields = ("user__username", "user__last_name", "email")

    fields = ("version", "status", "user", "email")


class ManagedPermissionRoleAutoGrantForm(forms.ModelForm):
    permissions = PermissionFormField(
        initial=0, widget=BitmaskSelect(choices=PERM_CHOICES_FOR_FIELD)
    )


class ManagedPermissionRoleAutoGrantInline(admin.TabularInline):
    form = ManagedPermissionRoleAutoGrantForm
    model = ManagedPermissionRoleAutoGrant
    extra = 1
    fields = ("role", "permissions")


@admin.register(ManagedPermission)
class ManagedPermissionAdmin(admin.ModelAdmin):
    list_display = (
        "description",
        "namespace",
        "group",
        "managable",
        "grant_mode",
        "created",
        "updated",
    )
    ordering = ("description",)
    search_fields = ("group", "description", "namespace")
    inlines = (ManagedPermissionRoleAutoGrantInline,)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return ("namespace",)
        return super().get_readonly_fields(request, obj)

    @reversion.create_revision()
    def save_formset(self, request, form, formset, change):
        return super().save_formset(request, form, formset, change)


@admin.register(OrganizationManagedPermission)
class OrganizationManagedPermissionAdmin(admin.ModelAdmin):
    list_display = (
        "org",
        "managed_permission",
        "reason",
        "product",
        "created",
    )
    autocomplete_fields = ("org",)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj=obj, **kwargs)
        form.base_fields[
            "managed_permission"
        ].queryset = ManagedPermission.objects.filter(grant_mode="restricted")
        return form


# need to unregister the existing user admin in order
# to implement our own with additional functionality
#
# user GrainyUserAdmin as base

try:
    admin.site.unregister(get_user_model())
except admin.sites.NotRegistered:
    pass


@admin.register(get_user_model())
class UserAdmin(UrlActionMixin, GrainyUserAdmin):
    list_display = GrainyUserAdmin.list_display + ("impersonate",)

    readonly_fields = GrainyUserAdmin.readonly_fields + ("impersonate",)
    search_fields = ("email", "first_name", "last_name", "username")

    actions = GrainyUserAdmin.actions + ("start_impersonation","stop_impersonation")

    def get_queryset(self, request):
        if is_impersonating(request):
            self.message_user(
                request,
                f"Currently impersonating {is_impersonating(request)}",
                messages.INFO,
            )

        return super().get_queryset(request)

    def impersonate(self, obj):
        with current_request() as request:
            user = is_impersonating(request)

            if user == obj:
                url = reverse(
                    "admin:auth_user_actions", args=(obj.id, "stop_impersonation")
                )
                return mark_safe(f'<a href="{url}">Stop</a>')
            if request.user == obj:
                return "-"

        url = reverse("admin:auth_user_actions", args=(obj.id, "start_impersonation"))
        return mark_safe(f'<a href="{url}">Start</a>')

    @admin.action(description="Impersonate user", permissions=["impersonate"])
    def start_impersonation(self, request, queryset):
        if queryset.count() > 1:
            self.message_user(
                request, "Please only select one user to impersonate", messages.ERROR
            )

        user = queryset.first()
        start_impersonation(request, user)

    @admin.action(description="Stop impersonating user", permissions=["impersonate"])
    def stop_impersonation(self, request, queryset):
        user = is_impersonating(request)

        if not user:
            return

        stop_impersonation(request)

        self.message_user(request, f"No longer impersonating {user}", messages.SUCCESS)

    def has_impersonate_permission(self, request):
        return request.user.is_superuser or request.perms.check("impersonate", "c")

@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "service", "type", "created", "updated", "status")
    search_fields = (
        "name",
        "email",
        "user__username",
        "user__first_name",
        "user__last_name",
        "user__email",
        "service__slug",
    )  #
    list_filter = ("type", "service")

    # Override the following methods to make the view read-only
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(ServiceFederationSupport)
class ServiceFederationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "federation_level", "selectable", "created", "updated")
    search_fields = ("name", "slug")


class ServiceURLInline(admin.TabularInline):
    model = FederatedServiceURL
    extra = 1
    fields = ("url", "service", "config")
    autocomplete_fields = ("service",)


@admin.register(AuthFederation)
class AuthFederationAdmin(admin.ModelAdmin):
    list_display = ("org", "application")
    search_fields = ("org__name", "org__slug")
    autocomplete_fields = ("org",)

    inlines = (ServiceURLInline,)

class FederatedServiceURLTagInline(admin.TabularInline):
    model = FederatedServiceURLTag
    extra = 1

@admin.register(FederatedServiceURL)
class FederatedServiceURLAdmin(admin.ModelAdmin):
    list_display = ("service", "org", "url")
    readonly_fields = ("org",)
    search_fields = ("service__name", "service__slug", "url", "auth__org__name", "auth__org__slug")
    inlines = (FederatedServiceURLTagInline,)

    def org(self, obj):
        return obj.auth.org