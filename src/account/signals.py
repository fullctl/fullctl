import fullctl.django.models.concrete.tasks as task_models
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_out
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import Signal, receiver
from django.shortcuts import render
from django.utils.translation import gettext as _
from oauth2_provider.models import AccessToken
from reversion.signals import post_revision_commit

from account.models import (
    APIKey,
    EmailConfirmation,
    ManagedPermission,
    ManagedPermissionRoleAutoGrant,
    Organization,
    OrganizationManagedPermission,
    OrganizationRole,
    OrganizationUser,
    Role,
    UpdatePermissions,
    UserPermissionOverride,
    UserSettings,
)
from common.email import email_noreply


@receiver(post_save, sender=Organization)
def sync_org(sender, **kwargs):
    task_models.CallCommand.create_task("aaactl_sync", "org", kwargs["instance"].id)


@receiver(post_save, sender=get_user_model())
def sync_user(sender, **kwargs):
    task_models.CallCommand.create_task("aaactl_sync", "user", kwargs["instance"].id)


@receiver(post_save, sender=OrganizationUser)
def sync_org_user_add(sender, **kwargs):
    task_models.CallCommand.create_task(
        "aaactl_sync", "org_user", kwargs["instance"].user_id
    )


@receiver(post_delete, sender=OrganizationUser)
def sync_org_user_delete(sender, **kwargs):
    task_models.CallCommand.create_task(
        "aaactl_sync", "org_user", kwargs["instance"].user_id
    )


create_user_config_signal = Signal()


@receiver(create_user_config_signal)
def create_user_config(sender, **kwargs):
    if kwargs.get("created"):
        user = kwargs.get("instance")
        if settings.ENABLE_EMAIL_CONFIRMATION:
            UserSettings.objects.get_or_create(user=user)
            EmailConfirmation.start(user)
        else:
            UserSettings.objects.get_or_create(user=user, email_confirmed=True)
        send_signup_notification(user, kwargs.get("application_instance"))


def send_signup_notification(user, application_instance):
    if not settings.SIGNUP_NOTIFICATION_EMAIL:
        return

    email_noreply(
        settings.SIGNUP_NOTIFICATION_EMAIL,
        _("New account registration"),
        render(
            None,
            "account/email/signup-notification.txt",
            {"user": user, "application_instance": application_instance},
        ).content.decode("utf-8"),
    )


@receiver(post_save, sender=get_user_model())
def generate_api_key(sender, **kwargs):
    if kwargs.get("created"):
        user = kwargs.get("instance")
        APIKey.objects.create(user=user, managed=True)


@receiver(post_save, sender=get_user_model())
def create_personal_org(sender, **kwargs):
    if kwargs.get("created"):
        user = kwargs.get("instance")
        Organization.personal_org(user)


@receiver(post_save, sender=get_user_model())
def auto_user_to_org(sender, **kwargs):
    if kwargs.get("created"):
        user = kwargs.get("instance")

        if not settings.AUTO_USER_TO_ORG:
            return

        org = Organization.objects.get(slug=settings.AUTO_USER_TO_ORG)
        OrganizationUser.objects.create(
            org=org,
            user=user,
        )

        org.set_as_default(user)

        ManagedPermission.apply_roles(org, user)


# @receiver(post_save, sender=get_user_model())
# def set_initial_permissions(sender, **kwargs):
#    if kwargs.get("created"):
#        user = kwargs.get("instance")
#        user.grainy_permissions.add_permission(f"user.{user.id}", "crud")


@receiver(post_delete, sender=ManagedPermissionRoleAutoGrant)
def delete_auto_grant(sender, **kwargs):
    UpdatePermissions.create_task_silent_limit()


@receiver(post_save, sender=OrganizationManagedPermission)
def set_org_manage_permission(sender, **kwargs):
    instance = kwargs.get("instance")
    UpdatePermissions.create_task_silent_limit(target_org=instance.org.id)


@receiver(post_delete, sender=OrganizationManagedPermission)
def delete_org_manage_permission(sender, **kwargs):
    instance = kwargs.get("instance")
    UpdatePermissions.create_task_silent_limit(target_org=instance.org.id)


@receiver(pre_delete, sender=OrganizationUser)
def delete_org_user(sender, **kwargs):
    instance = kwargs.get("instance")
    OrganizationRole.objects.filter(user=instance.user, org=instance.org).delete()


@receiver(post_save, sender=OrganizationUser)
def save_org_user(sender, **kwargs):
    instance = kwargs.get("instance")
    created = kwargs.get("created")

    if not created:
        return

    if instance.org.org_user_set.count() == 1:
        qset = Role.objects.filter(auto_set_on_creator=True)
    else:
        qset = Role.objects.filter(auto_set_on_member=True)

    for role in qset:
        OrganizationRole.objects.get_or_create(
            user=instance.user, org=instance.org, role=role
        )


@receiver(post_delete, sender=OrganizationRole)
def del_org_role(sender, **kwargs):
    instance = kwargs.get("instance")
    ManagedPermission.apply_roles(instance.org, instance.user)


@receiver(post_delete, sender=UserPermissionOverride)
def del_user_permission_override(sender, **kwargs):
    instance = kwargs.get("instance")
    instance.user.grainy_permissions.filter(namespace=instance.namespace).delete()
    ManagedPermission.apply_roles(instance.org, instance.user)


def sync_roles(**kwargs):
    update_all_permissions = False

    for vs in kwargs.get("versions"):
        instance = vs.object
        if isinstance(instance, (OrganizationRole, UserPermissionOverride)):
            ManagedPermission.apply_roles(instance.org, instance.user)
        elif isinstance(instance, ManagedPermissionRoleAutoGrant):
            update_all_permissions = True

    if update_all_permissions:
        UpdatePermissions.create_task_silent_limit()


post_revision_commit.connect(sync_roles)


@receiver(user_logged_out)
def delete_user_access_tokens(sender, user, request, **kwargs):
    # Find and delete all access tokens associated with the user
    AccessToken.objects.filter(user=user).delete()
