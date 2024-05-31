import re

import fullctl.django.enum as enum
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.utils.translation import gettext as _
from django_recaptcha.fields import ReCaptchaField

from account.models import ContactMessage, Organization, OrganizationRole
from account.models import PasswordReset as PasswordResetModel
from account.validators import validate_password
from applications.models import Service


class Login(forms.Form):
    username_or_email = forms.CharField()
    password = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        username_or_email = self.cleaned_data["username_or_email"].lower()
        return username_or_email


class UserInformationBase(forms.Form):
    username = forms.CharField(validators=[UnicodeUsernameValidator])
    first_name = forms.CharField()
    last_name = forms.CharField()
    email = forms.EmailField()

    def clean_username(self):
        username = self.cleaned_data["username"].lower()

        User = get_user_model()

        other_user = User.objects.filter(username=username).first()
        user = getattr(self, "user", None)

        if user and other_user and other_user.id != user.id:
            raise forms.ValidationError(_("Username not available"))

        return username


class UserSettings(forms.Form):
    opt_promotions = forms.BooleanField(
        required=False, label=_("Notify me about product updates and offers")
    )


class RegisterUser(UserInformationBase, forms.Form):
    password = forms.CharField(widget=forms.PasswordInput)
    password_confirmation = forms.CharField(widget=forms.PasswordInput)
    captcha = ReCaptchaField()

    def clean_password(self):
        password = self.cleaned_data["password"]

        return validate_password(password)

    def clean_email(self):
        email = self.cleaned_data["email"]
        if get_user_model().objects.filter(email=email).exists():
            raise forms.ValidationError(_("User with this email already registered"))
        return email

    def clean(self):
        cleaned_data = super().clean()

        password = cleaned_data.get("password")
        if password and password != cleaned_data.get("password_confirmation"):
            raise forms.ValidationError(
                {
                    "password_confirmation": _(
                        "Password confirmation needs to match password"
                    )
                }
            )
        return cleaned_data


class PasswordProtectedForm(forms.Form):
    password = forms.CharField(widget=forms.PasswordInput, label=_("Password"))

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_password(self):
        password = self.cleaned_data["password"]
        if not self.user.check_password(password):
            raise forms.ValidationError(_("Incorrect password"))
        return password


class ChangePasswordBase(forms.Form):
    password_new = forms.CharField(widget=forms.PasswordInput, label=_("New Password"))
    password_confirmation = forms.CharField(
        widget=forms.PasswordInput, label=_("Confirm Password")
    )

    def clean_password_new(self):
        password = self.cleaned_data["password_new"]
        validate_password(password)
        return password

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password_new") != cleaned_data.get(
            "password_confirmation"
        ):
            raise forms.ValidationError(
                {
                    "password_confirmation": _(
                        "Password confirmation needs to match password"
                    )
                }
            )
        return cleaned_data


class ChangePassword(ChangePasswordBase, PasswordProtectedForm):
    pass


class PasswordReset(ChangePasswordBase):
    secret = forms.CharField(label=_("Secret"), widget=forms.HiddenInput)

    def clean_secret(self):
        secret = self.cleaned_data["secret"]

        try:
            self.cleaned_data["password_reset"] = PasswordResetModel.objects.get(
                secret=secret
            )
        except PasswordResetModel.DoesNotExist:
            raise forms.ValidationError(_("Invalid secret"))

        return secret


class StartPasswordReset(forms.Form):
    email = forms.EmailField(label=_("Email address"))


class ChangeInformation(UserInformationBase, PasswordProtectedForm):
    pass


class CreateOrganization(forms.Form):
    name = forms.CharField(label=_("Organization Name"))
    slug = forms.CharField(label=_("Slug (url-friendly token name)"), required=False)

    BLOCKED_SLUG_VALUES = [
        "api",
        "test",
        "media",
        "admin",
        "billing",
        "social",
        "account",
        "accounts",
    ]

    def clean_slug(self):
        slug = self.cleaned_data["slug"].lower()

        if re.search("[^-_a-z0-9]", slug):
            raise forms.ValidationError(
                _("May only contain the following characters: -, _, a-Z and 0-9")
            )

        if slug in self.BLOCKED_SLUG_VALUES:
            raise forms.ValidationError(_("This name is reserved and may not be used"))

        slug = Organization().clean_slug(slug)

        return slug


class EditOrganization(CreateOrganization):
    def __init__(self, org, *args, **kwargs):
        self.org = org
        super().__init__(*args, **kwargs)

        if org.user_id:
            self.fields["name"].widget.attrs["readonly"] = True
            self.fields["slug"].widget.attrs["readonly"] = True
            self.initial["name"] = org.user.username + " (Personal)"


class EditOrganizationPasswordProtected(PasswordProtectedForm, EditOrganization):
    pass


class InviteToOrganization(forms.Form):
    email = forms.EmailField(label=_("Email address"))
    service = forms.ModelChoiceField(
        Service.objects.filter(status="ok"),
        required=False,
        label=_("Service redirect"),
        widget=forms.HiddenInput,
    )
    is_admin_invite = forms.BooleanField(label=_("Invite as Org Admin"), required=False)

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user", None)
        self.org = kwargs.pop("org", None)

        super().__init__(*args, **kwargs)

        try:
            OrganizationRole.objects.get(
                org=self.org, user=self.user, role__name="Admin"
            )
        except OrganizationRole.DoesNotExist:
            del self.fields["is_admin_invite"]


class CreateOrgAPIKey(forms.Form):
    name = forms.CharField(label=_("Name / Description"))
    email = forms.EmailField(label=_("Email address"))


class CreateAPIKey(forms.Form):
    name = forms.CharField(label=_("Name / Description"))
    readonly = forms.BooleanField(label=_("Read only"), required=False)


class Contact(forms.ModelForm):
    name = forms.CharField(label=_("Name"))
    email = forms.EmailField(label=_("Email address"))
    message = forms.JSONField(label=_("Message"))
    type = forms.ChoiceField(choices=enum.CONTACT_MESSAGE_TYPE, required=False)

    class Meta:
        model = ContactMessage
        fields = ["name", "email", "message"]
