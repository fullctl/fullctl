import datetime
import secrets
from typing import Literal

import reversion
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import models
from django.shortcuts import render
from django.urls import reverse
from django.utils.translation import gettext as _
from django_grainy.decorators import grainy_model
from django_grainy.models import (
    Permission,
    PermissionField,
    PermissionManager,
    UserPermission,
)
from django_grainy.util import Permissions
from fullctl.django.enum import CONTACT_MESSAGE_TYPE
from pydantic import BaseModel
from pydantic import ValidationError as PydanticValidationError
from pydantic import model_validator

from account.models.federation import FederatedServiceURL  # noqa F401

# imports needed for initialization
from account.tasks import UpdatePermissions  # noqa F401
from common.email import email_contact_us, email_noreply
from common.models import HandleRefModel

# Create your models here.


@reversion.register
class UserSettings(HandleRefModel):
    """
    Extra user fields
    """

    user = models.OneToOneField(
        get_user_model(), on_delete=models.CASCADE, related_name="user_settings"
    )
    email_confirmed = models.BooleanField(
        default=False, help_text=_("Has the user confirmed his email")
    )
    opt_promotions = models.BooleanField(
        default=True, help_text=_("User is opted in for promotional notifications")
    )

    class Meta:
        db_table = "account_user_settings"
        verbose_name = _("User Settings")
        verbose_name_plural = _("User Settings")

    class HandleRef:
        tag = "user_settings"


def generate_org_name():
    i = 0
    while i < 1000:
        name = secrets.token_urlsafe(8)
        if not Organization.objects.filter(name=name).exists():
            return name
        i += 1
    raise OSError(_("Unable to generate unique organization name"))


def generate_org_slug():
    i = 0
    while i < 1000:
        slug = secrets.token_urlsafe(8).lower()
        if not Organization.objects.filter(slug=slug).exists():
            return slug
        i += 1
    raise OSError(_("Unable to generate unique organization slug"))


@reversion.register
@grainy_model(namespace="org")
class Organization(HandleRefModel):
    name = models.CharField(max_length=255, unique=True, default=generate_org_name)
    slug = models.CharField(max_length=255, unique=True, default=generate_org_slug)
    user = models.OneToOneField(
        get_user_model(),
        on_delete=models.SET_NULL,
        related_name="personal_org",
        blank=True,
        null=True,
        unique=True,
        help_text=_(
            "If set, designates this organzation as a user's personal organization"
        ),
    )

    class Meta:
        db_table = "account_organization"
        verbose_name = _("Organization")
        verbose_name_plural = _("Organizations")

    class HandleRef:
        tag = "org"

    @classmethod
    def personal_org(cls, user):
        """
        returns the personal org for the user

        will create the org if it does not exist
        """

        try:
            return user.org_user_set.get(org__user_id=user.id).org
        except OrganizationUser.DoesNotExist:
            pass

        org = cls.objects.create(user=user, name=user.username)
        org.add_user(user, "crud")

        return org

    @classmethod
    def default_org(cls, user):
        """
        Returns the default organization for the user.

        If the user has not specified a default organization, the user's personal
        organization will be returned,
        """

        default_org = user.org_user_set.filter(is_default=True)

        if default_org.exists():
            return default_org.first().org

        return cls.personal_org(user)

    @classmethod
    def get_for_user(cls, user, perms="r"):
        return Permissions(user).instances(cls, perms, ignore_grant_all=True)

    @property
    def permission_namespaces(self):
        if not hasattr(self, "_permission_namespaces"):
            mperms = ManagedPermission.objects.filter(status="ok", group="aaactl")
            r = []
            for mperm in mperms:
                r.append(mperm.namespace)
            self._permission_namespaces = r

        return self._permission_namespaces

    @property
    def users(self):
        for org_user in self.org_user_set.all():
            yield org_user.user

    @property
    def label(self):
        if self.user_id:
            return f"{self.user.username} (Personal)"
        return self.name

    @property
    def label_long(self):
        if self.user_id:
            return _("Your Personal Organization")
        return self.name

    @property
    def is_personal(self):
        return self.user_id is not None

    def __str__(self):
        return self.label

    @reversion.create_revision()
    def add_user(self, user, perms="r"):
        org_user, created = OrganizationUser.objects.get_or_create(org=self, user=user)
        if created:
            if user.org_user_set.count() == 2:
                # switch from personal org to real org as primary org
                org_user.is_default = True
                org_user.save()

        return org_user

    @reversion.create_revision()
    def remove_user(self, user):
        self.org_user_set.filter(user=user).delete()

    def clean_slug(self, value):
        value = value.lower()
        protected_values = ["personal"]
        if value in protected_values:
            raise ValidationError(_("Protected value: {}").format(value))
        return value

    def set_as_default(self, user):
        """
        Makes this organization the default organization for the user
        """

        org_user = user.org_user_set.filter(org=self).first()

        if not org_user:
            raise KeyError("Not a member of this organization")

        # set new default org
        org_user.is_default = True
        org_user.save()


@reversion.register
class OrganizationUser(HandleRefModel):
    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, related_name="org_user_set"
    )
    org = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="org_user_set"
    )

    is_default = models.BooleanField(
        default=False,
        help_text=_("This organization is the user's designated default organization"),
    )

    class Meta:
        db_table = "account_organization_user"
        verbose_name = _("Organization User Membership")
        verbose_name_plural = _("Organization User Memberships")

    class HandleRef:
        tag = "org_user"

    def __str__(self):
        return f"{self.org.slug}:{self.user.username} ({self.id})"

    def save(self, **kwargs):
        if self.is_default:
            self.user.org_user_set.exclude(id=self.id).update(is_default=False)
        super().save(**kwargs)


@reversion.register
class Role(HandleRefModel):
    name = models.CharField(max_length=255, unique=True)
    description = models.CharField(max_length=255, null=True, blank=True)
    level = models.PositiveIntegerField(
        help_text=_(
            "Defines the order in which permissions are applied for user's that are in multiple roles. With the lowest level role being applied last."
        )
    )
    auto_set_on_creator = models.BooleanField(
        help_text=_("Automatically give the creators of an organization this role"),
        default=False,
    )
    auto_set_on_member = models.BooleanField(
        help_text=_("Automatically give new members of an organization this role"),
        default=False,
    )

    class Meta:
        db_table = "account_role"
        verbose_name = _("Role")
        verbose_name_plural = _("Roles")

    class HandleRef:
        tag = "role"

    def __str__(self):
        return f"Role: {self.name} ({self.id})"


@reversion.register
class OrganizationRole(HandleRefModel):
    org = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="roles"
    )
    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, related_name="roles"
    )
    role = models.ForeignKey(
        Role, on_delete=models.PROTECT, related_name="organization_roles"
    )

    class Meta:
        db_table = "account_organization_user_role"
        verbose_name = _("User role within organization")
        verbose_name_plural = _("User roles within organization")
        unique_together = (("org", "user", "role"),)

    class HandleRef:
        tag = "org_user_role"


def generate_api_key():
    i = 0
    while i < 1000:
        key = secrets.token_urlsafe()
        if not APIKey.objects.filter(key=key).exists():
            return key
        i += 1
    raise OSError(_("Unable to generate unique api key"))


class APIKeyBase(HandleRefModel):
    name = models.CharField(max_length=255, blank=True, null=True)
    key = models.CharField(max_length=255, default=generate_api_key, unique=True)
    managed = models.BooleanField(
        default=True, help_text=_("Is the API Key managed by the owner")
    )

    class Meta:
        abstract = True

    @property
    def is_authenticated(self):
        return True

    @property
    def key_id(self):
        return self.key[:8]

    def __str__(self):
        return f"{self.key_id} ({self.id})"


@reversion.register
@grainy_model(namespace="key")
class APIKey(APIKeyBase):
    """
    Describes a personal APIKey
    """

    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, related_name="key_set"
    )
    readonly = models.BooleanField(default=False)

    class Meta:
        db_table = "account_api_key"
        verbose_name = _("Personal API Key")
        verbose_name_plural = _("Personal API Keys")

    class HandleRef:
        tag = "key"


@reversion.register
class APIKeyPermission(HandleRefModel, Permission):
    """
    Describes API key permissions
    """

    api_key = models.ForeignKey(
        APIKey, on_delete=models.CASCADE, related_name="grainy_permissions"
    )

    objects = PermissionManager()

    class Meta:
        db_table = "account_api_key_permission"
        verbose_name = _("API Key Permission")
        verbose_name_plural = _("API Key Permissions")

    class HandleRef:
        tag = "key_permission"


@reversion.register
@grainy_model(namespace="_key_")
class InternalAPIKey(APIKeyBase):
    """
    Describes internal APIKey
    """

    class Meta:
        db_table = "account_internal_api_key"
        verbose_name = _("Internal API Key")
        verbose_name_plural = _("Internal API Keys")

    class HandleRef:
        tag = "_key_"

    @classmethod
    def require(cls):
        if not cls.objects.all().count():
            key = cls.objects.create()
            key.grainy_permissions.add_permission("*.*", "crud")


@reversion.register
class InternalAPIKeyPermission(HandleRefModel, Permission):
    """
    Describes API key permissions
    """

    api_key = models.ForeignKey(
        InternalAPIKey, on_delete=models.CASCADE, related_name="grainy_permissions"
    )

    objects = PermissionManager()

    class Meta:
        db_table = "account_internal_api_key_permission"
        verbose_name = _("Internal API Key Permission")
        verbose_name_plural = _("Internal API Key Permissions")

    class HandleRef:
        tag = "key_permission"


@reversion.register
@grainy_model(namespace="org_key", namespace_instance="{namespace}.{instance.org_id}")
class OrganizationAPIKey(APIKeyBase):
    """
    Describes a organization APIKey
    """

    org = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="org_key_set"
    )
    email = models.EmailField()

    class Meta:
        db_table = "account_org_api_key"
        verbose_name = _("Organization API Key")
        verbose_name_plural = _("Organization API Keys")

    class HandleRef:
        tag = "org_key"


@reversion.register
class OrganizationAPIKeyPermission(HandleRefModel, Permission):
    """
    Describes organization API key permissions
    """

    api_key = models.ForeignKey(
        OrganizationAPIKey, on_delete=models.CASCADE, related_name="grainy_permissions"
    )

    objects = PermissionManager()

    class Meta:
        db_table = "account_org_api_key_permission"
        verbose_name = _("Organization API Key Permission")
        verbose_name_plural = _("Organization API Key Permissions")

    class HandleRef:
        tag = "org_key_permission"

    def __str__(self):
        return f"{self.namespace} ({self.id})"


def generate_email_confirmation_secret():
    i = 0
    while i < 1000:
        secret = secrets.token_urlsafe()
        if not EmailConfirmation.objects.filter(secret=secret).exists():
            return secret
        i += 1
    raise OSError(_("Unable to generate unique email confirmation secret"))


@reversion.register
class EmailConfirmation(HandleRefModel):
    """
    Describes email confirmation process
    """

    user = models.OneToOneField(
        get_user_model(), on_delete=models.CASCADE, related_name="email_confirmation"
    )

    secret = models.CharField(
        max_length=255, default=generate_email_confirmation_secret
    )

    email = models.EmailField()

    class Meta:
        db_table = "account_email_confirmation"
        verbose_name = _("Email Confirmation Process")
        verbose_name_plural = _("Email Confirmation Processes")

    class HandleRef:
        tag = "email_confirmation"

    @classmethod
    def start(cls, user):
        if not settings.ENABLE_EMAIL_CONFIRMATION:
            return

        try:
            user.email_confirmation.delete()
        except cls.DoesNotExist:
            pass

        with reversion.create_revision():
            instance = cls.objects.create(user=user, email=user.email, status="pending")

        email_noreply(
            user.email,
            _("Confirm your email address"),
            render(
                None, "account/email/confirm-email.txt", {"instance": instance}
            ).content.decode("utf-8"),
        )

        return instance

    @property
    def url(self):
        return "{}{}".format(
            settings.AAACTL_URL,
            reverse("account:auth-confirm-email", args=(self.secret,)),
        )

    @reversion.create_revision()
    def complete(self):
        user_settings, _ = UserSettings.objects.get_or_create(user=self.user)
        user_settings.email_confirmed = True
        user_settings.save()

        self.delete()


def generate_password_reset_secret():
    i = 0
    while i < 1000:
        secret = secrets.token_urlsafe()
        if not PasswordReset.objects.filter(secret=secret).exists():
            return secret
        i += 1
    raise OSError(_("Unable to generate unique password reset secret"))


@reversion.register
class PasswordReset(HandleRefModel):
    """
    Describes password reset process
    """

    user = models.OneToOneField(
        get_user_model(), on_delete=models.CASCADE, related_name="password_reset"
    )

    secret = models.CharField(max_length=255, default=generate_password_reset_secret)

    email = models.EmailField()

    class Meta:
        db_table = "account_password_reset"
        verbose_name = _("Password Reset Process")
        verbose_name_plural = _("Password Reset Processes")

    class HandleRef:
        tag = "password_reset"

    @classmethod
    def start(cls, user):
        try:
            user.password_reset.delete()
        except cls.DoesNotExist:
            pass

        with reversion.create_revision():
            instance = cls.objects.create(user=user, email=user.email, status="pending")

        email_noreply(
            user.email,
            _("Password Reset"),
            render(
                None, "account/email/password-reset.txt", {"instance": instance}
            ).content.decode("utf-8"),
        )

        return instance

    @property
    def expired(self):
        delta = datetime.datetime.now(datetime.timezone.utc) - self.created
        return delta.hours >= 1

    @property
    def url(self):
        return "{}{}".format(
            settings.AAACTL_URL,
            reverse("account:auth-reset-password", args=(self.secret,)),
        )

    @reversion.create_revision()
    def complete(self, new_password):
        self.user.set_password(new_password)
        self.user.save()
        self.delete()


def generate_invite_secret():
    i = 0
    while i < 1000:
        secret = secrets.token_urlsafe()
        if not Invitation.objects.filter(secret=secret).exists():
            return secret
        i += 1
    raise OSError(_("Unable to generate unique invitation secret"))


@reversion.register
class UserPermissionOverride(HandleRefModel):
    """
    Describes a permission override for a user
    usually set by manually granting a permission level
    directly to the user through the dashboard interface
    """

    user = models.ForeignKey(
        get_user_model(), related_name="permission_overrides", on_delete=models.CASCADE
    )
    org = models.ForeignKey(
        Organization,
        null=True,
        blank=True,
        related_name="permission_overrides",
        on_delete=models.CASCADE,
    )
    namespace = models.CharField(max_length=255)
    permissions = PermissionField()

    class Meta:
        verbose_name = _("User permission override")
        verbose_name_plural = _("User permission overrides")
        unique_together = (("user", "org", "namespace"),)

    def apply(self):
        self.user.grainy_permissions.add_permission(self.namespace, self.permissions)


@reversion.register
class ManagedPermission(HandleRefModel):
    """
    Describes a custom permission definition, allowing
    to add app / service specific permissions to be managed
    through aaactl
    """

    namespace = models.CharField(
        max_length=255,
        help_text=_(
            "The permission namespace. The following variables are available for formatting: {org_id}"
        ),
    )

    group = models.CharField(
        max_length=255, help_text=_("Belongs to this group of permissions")
    )

    description = models.CharField(
        max_length=255, help_text=_("What is this permission namespace used for?")
    )

    managable = models.BooleanField(
        default=True, help_text=_("Can organization admins manage this permission?")
    )

    grant_mode = models.CharField(
        max_length=16,
        default="auto",
        choices=(
            ("auto", _("Automatically")),
            ("restricted", _("Restricted")),
        ),
        help_text=_("How is this permission granted"),
    )

    class Meta:
        db_table = "account_managed_permission"
        verbose_name = _("Managed permission")
        verbose_name_plural = _("Managed permissions")

    class HandleRef:
        tag = "mperm"

    @classmethod
    def apply_roles(cls, org, user, delete_permissions=True):
        user_roles = [ur.role_id for ur in user.roles.filter(org=org)]
        # delete all those namespaces for the user in the org
        if delete_permissions and org:
            for ns in cls.namespaces():
                user.grainy_permissions.delete_permission(ns.format(org_id=org.id))

        # re-apply automatically granted permissions through roles
        for auto_grant in ManagedPermissionRoleAutoGrant.objects.filter(
            role__in=user_roles
        ).order_by("-role__level"):
            managed_permission = auto_grant.managed_permission

            if not managed_permission.can_grant_to_org(org):
                continue

            ns = managed_permission.namespace.format(org_id=org.id)
            user.grainy_permissions.add_permission(ns, auto_grant.permissions)

        # re-apply permission overrides
        for override in UserPermissionOverride.objects.filter(user=user):
            override.apply()

    @classmethod
    def apply_roles_all(cls):
        """
        Reapplies roles for all users across all orgs

        TODO: This is a costly operation, and should eventually be replaced
        with something that does batch inserts, especially once the
        number of active users grow.

        Alternatively call it from a task. Or both.
        """

        org_qset = Organization.objects.all()

        # delete all user permissions
        UserPermission.objects.all().delete()

        for org in org_qset:
            for user in org.org_user_set.all().select_related("user", "org"):
                cls.apply_roles(org, user.user, delete_permissions=False)

    @classmethod
    def apply_roles_org(cls, org):
        """
        Takes an organization id and re-applies permissions for all
        users in the organization.
        """
        for user in org.org_user_set.all().select_related("user", "org"):
            cls.apply_roles(org, user.user)

    @classmethod
    def namespaces(cls):
        for managed_permission in cls.objects.all():
            yield managed_permission.namespace

    def __str__(self):
        return f"{self.group} - {self.description}"

    def can_grant_to_org(self, org):
        if self.grant_mode == "auto":
            return True

        if self.grant_mode == "restricted":
            return org.org_managed_permission_set.filter(
                managed_permission=self
            ).exists()

        raise ValueError(f"Invalid value for grant_mode: {self.grant_mode}")


@reversion.register
class ManagedPermissionRoleAutoGrant(HandleRefModel):
    managed_permission = models.ForeignKey(
        ManagedPermission, related_name="role_auto_grants", on_delete=models.CASCADE
    )
    role = models.ForeignKey(
        Role, related_name="managed_permissions", on_delete=models.CASCADE
    )
    permissions = PermissionField(
        help_text=_("Will grand this level of permissions to the specified role")
    )

    class Meta:
        db_table = "account_managed_permission_role_auto_grant"
        verbose_name = _("Permission assignment for role")
        verbose_name_plural = _("Permission assignments for roles")
        unique_together = (("managed_permission", "role"),)

    class HandleRef:
        tag = "managed_permission_role_auto_grant"


@reversion.register
class OrganizationManagedPermission(HandleRefModel):
    """
    Describes a relationship of an organization to a `restricted` ManagedPermission
    """

    org = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="org_managed_permission_set",
    )

    managed_permission = models.ForeignKey(
        ManagedPermission,
        on_delete=models.CASCADE,
        related_name="org_managed_permission_set",
    )

    reason = models.CharField(
        max_length=255,
        help_text=_("Reason organization was granted to manage this permission"),
    )

    product = models.ForeignKey(
        "billing.OrganizationProduct",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        help_text=_("Perimission management enabled through product"),
    )

    class HandleRef:
        tag = "org_managed_permission"

    class Meta:
        db_table = "account_org_managed_permissions"
        verbose_name = _("Managed permission for organization")
        verbose_name_plural = _("Managed permissions for organization")


@reversion.register
class Invitation(HandleRefModel):
    secret = models.CharField(max_length=255, default=generate_invite_secret)
    org = models.ForeignKey(
        Organization, on_delete=models.CASCADE, related_name="invite_set"
    )
    created_by = models.ForeignKey(
        get_user_model(),
        null=True,
        blank=False,
        on_delete=models.SET_NULL,
        related_name="invite_set",
    )
    email = models.EmailField()
    service = models.ForeignKey(
        "applications.Service",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invite_set",
    )
    role = models.CharField(
        choices=(("member", "Member"), ("admin", "Admin")),
        default="member",
        max_length=10,
    )
    expiry = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "account_invitation"
        verbose_name = _("Invitation")
        verbose_name_plural = _("Invitations")

    class HandleRef:
        tag = "invite"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def update_expiry_date(self):
        self.expiry = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(
            days=settings.INVITE_EXPIRY
        )

    @property
    def expired(self):
        if not self.expiry:
            # invitations that don't have expiry set are from before
            # we introduced the expiry feature, so we assume they are
            # expired
            return True
        return self.expiry < datetime.datetime.now(datetime.timezone.utc)

    @property
    def url(self):
        return "{}{}".format(
            settings.AAACTL_URL, reverse("account:accept-invite", args=(self.secret,))
        )

    def __str__(self):
        return f"{self.org.slug}:{self.email} ({self.id})"

    def save(self, *args, **kwargs):
        if self.role == "admin" and not self._is_inviter_admin():
            raise PermissionError("Only admins can invite other admins")
        self.update_expiry_date()
        super().save(*args, **kwargs)

    def send(self):
        # check if the user is allowed to invite admins
        if not self._is_inviter_admin() and self.role == "admin":
            raise PermissionError("Only admins can invite other admins")

        if self.created_by:
            inviting_person = self.created_by.get_full_name()
        else:
            inviting_person = "[Deleted user]"
        email_noreply(
            self.email,
            _("Invitation to join {}").format(self.org.label),
            render(
                None,
                "account/email/invite.txt",
                {
                    "invite": self,
                    "inviting_person": inviting_person,
                    "org": self.org,
                    "host": settings.AAACTL_URL,
                    "signature": settings.EMAIL_SIGNATURE,
                },
            ).content.decode("utf-8"),
        )
        self.update_expiry_date()

    @reversion.create_revision()
    def complete(self, user):
        if not self.expired and not self.org.org_user_set.filter(user=user).exists():
            if self.role == "admin":
                if self._is_inviter_admin():
                    self.org.add_user(user, "crud")
                    # TODO: think about how to add Admin role if roles are user defined
                    role = Role.objects.get(name="Admin")
                    OrganizationRole.objects.get_or_create(
                        org=self.org, user=user, role=role
                    )
                else:
                    raise PermissionError("Only admins can invite other admins")
            else:
                self.org.add_user(user, "r")

        Invitation.objects.filter(org=self.org, email=self.email).delete()

    def _is_inviter_admin(self):
        try:
            OrganizationRole.objects.get(
                org=self.org, user=self.created_by, role__name="Admin"
            )
            return True
        except OrganizationRole.DoesNotExist:
            return False


class Impersonation(models.Model):
    superuser = models.OneToOneField(
        get_user_model(), on_delete=models.CASCADE, related_name="impersonating"
    )
    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, related_name="impersonated_by"
    )

    class Meta:
        db_table = "account_impersonation"
        verbose_name = _("Impersonation")
        verbose_name_plural = _("Impersonations")


class ContactMessage(HandleRefModel):
    """
    A message sent to us from a user or anonymous user
    """

    user = models.ForeignKey(
        get_user_model(), on_delete=models.CASCADE, null=True, blank=True
    )
    email = models.EmailField(null=True, blank=True)
    name = models.CharField(max_length=255, null=True, blank=True)
    type = models.CharField(
        max_length=255, choices=CONTACT_MESSAGE_TYPE, default="general"
    )
    message = models.JSONField()
    service = models.ForeignKey(
        "applications.Service",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="contact_message_set",
    )

    class Meta:
        db_table = "account_contact_message"
        verbose_name = _("Contact message")
        verbose_name_plural = _("Contact messages")

    class HandleRef:
        tag = "contact_message"

    def __str__(self):
        return f"{self.name} - {self.email} - {self.created}"

    def notify(self):
        """
        Sends a notification to the CONTACT_US_EMAIL address
        specified in settings
        """

        email_contact_us(
            self.email,
            _("Contact message from {}").format(self.name),
            render(
                None,
                "account/email/contact-message.txt",
                {"message": self},
            ).content.decode("utf-8"),
        )


class PocConfigData(BaseModel):
    service: Literal["ixctl", "peerctl"]
    delivery_type: str
    recipients: list[str]

    @model_validator(mode="after")
    def validate_recipients(self):
        if len(self.recipients) < 1:
            raise ValueError(_("Recipients must contain at least one item."))

        if self.delivery_type == "email":
            for recipient in self.recipients:
                try:
                    validate_email(recipient)
                except ValidationError:
                    raise ValueError(_(f"'{recipient}' is not a valid email address."))

        return self


class PointOfContact(models.Model):
    org = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="org_poc_set",
    )
    delivery_type = models.CharField(
        default="email",
        choices=(("email", _("Email")),),
        help_text=_("The type of message delivery for the alert."),
    )
    config = models.JSONField(help_text="Configurations for the alert.", default=list)
    type = models.CharField(
        default="notifications",
        choices=(
            ("general", _("General")),
            ("notifications", _("Notifications")),
        ),
        help_text=_("Point of contact type."),
    )
    status = models.CharField(
        default="ok",
        choices=(
            ("ok", _("Ok")),
            ("inactive", _("Inactive")),
        ),
    )

    class HandleRef:
        tag = "poc"

    def clean(self):
        super().clean()

        if not isinstance(self.config, list):
            raise ValidationError("Config must be a list.")

        try:
            for config in self.config:
                PocConfigData(**config, delivery_type=self.delivery_type)
        except PydanticValidationError as ex:
            raise ValidationError(str(ex))

        if (
            PointOfContact.objects.exclude(pk=self.pk)
            .filter(org=self.org, delivery_type=self.delivery_type, type=self.type)
            .exists()
        ):
            raise ValidationError(
                "Delivery method for that contact type already exists."
            )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
