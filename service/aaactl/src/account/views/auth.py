import logging
import time
from urllib.parse import urlencode, urlparse

import account.forms
from account.models import (
    EmailConfirmation,
    Invitation,
    Organization,
    PasswordReset,
    effective_mfa_policy,
    mfa_setup_required_message,
    orgs_enforcing,
    user_has_satisfying_2fa,
)
from account.session import set_selected_org
from applications.models import Service
from common.util import format_logo_url
from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth import login as fn_login
from django.contrib.auth import logout as fn_logout
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.urls import resolve, reverse
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.generic import FormView
from django_security_keys.ext.two_factor.views import DisableView as BaseDisableView
from django_security_keys.ext.two_factor.views import LoginView as TwoFactorLoginView
from django_security_keys.ext.two_factor.views import SetupView as BaseSetupView
from oauth2_provider.oauth2_backends import get_oauthlib_core
from rest_framework_simplejwt.tokens import RefreshToken
from two_factor.views import BackupTokensView as BaseBackupTokensView
from two_factor.views import ProfileView as BaseProfileView
from whitelabel_fullctl.models import OrganizationBranding

log = logging.getLogger(__name__)

# Create your views here.


def valid_redirect(path, fallback):
    if not path:
        return fallback

    parts = urlparse(path)

    try:
        resolve(parts.path)
    except Http404:
        return fallback

    return path


def get_fallback_url(user):
    default = reverse("account:controlpanel")
    org = Organization.default_org(user)

    redirect_to_service = getattr(settings, "REDIRECT_TO_SERVICE")
    if not redirect_to_service:
        return default

    try:
        service = Service.objects.get(name=redirect_to_service)
        return service.service_url.replace("{org.slug}", org.slug)
    except Service.DoesNotExist:
        log.error(f"Service {redirect_to_service} not found.")

    return default


def login_support(request):
    """
    Redirect to fullctl OAuth login for support staff.
    Alias for /social/login/fullctl/
    """
    next_param = request.GET.get("next", "")
    redirect_url = reverse("social:begin", kwargs={"backend": "fullctl"})
    if next_param:
        redirect_url = f"{redirect_url}?{urlencode({'next': next_param})}"
    return redirect(redirect_url)


def _branding_context(request):
    """
    Build the aaactl branding/social-auth context shared by login & wizard
    views. Pulled out of the legacy login() function so the new wizard-based
    LoginView can inject the same context into two_factor's templates.
    """
    env = {}
    branding_org = getattr(settings, "BRANDING_ORG", None)
    http_host = request.get_host()
    org_branding = None
    org_branding_components = {}

    if branding_org:
        org_branding = OrganizationBranding.objects.filter(
            org__slug=branding_org
        ).first()
    elif http_host:
        org_branding = OrganizationBranding.objects.filter(http_host=http_host).first()

    if org_branding:
        org_branding_components = {
            "name": org_branding.org.name,
            "html_footer": org_branding.html_footer,
            "css": org_branding.css,
            "dark_logo_url": format_logo_url(org_branding.dark_logo_url),
            "light_logo_url": format_logo_url(org_branding.light_logo_url),
            "favicon_url": format_logo_url(org_branding.favicon_url),
            "custom_org": True,
        }

    oauth_enabled = any(
        [
            getattr(settings, "SOCIAL_AUTH_GOOGLE_OAUTH2_ENABLED", False),
            getattr(settings, "SOCIAL_AUTH_PEERINGDB_ENABLED", False),
            getattr(settings, "SOCIAL_AUTH_OKTA_OPENIDCONNECT_ENABLED", False),
            getattr(settings, "SOCIAL_AUTH_FULLCTL_ENABLED", False),
        ]
    )

    invite_secret = request.GET.get("invite")
    if invite_secret:
        try:
            env["invite"] = Invitation.objects.get(secret=invite_secret)
        except Invitation.DoesNotExist:
            messages.error(request, _("Invitation not found"))

    env.update(
        password_login_enabled=settings.PASSWORD_LOGIN_ENABLED,
        org_branding=org_branding_components,
        show_register_link=getattr(settings, "ENABLE_ACCOUNT_REGISTRATION", True),
        oauth_enabled=oauth_enabled,
        show_peeringdb_text=settings.SOCIAL_AUTH_PEERINGDB_ENABLED,
        hide_fullctl_oauth=settings.SOCIAL_AUTH_FULLCTL_HIDDEN_FROM_LOGIN,
    )
    return env


class LoginView(TwoFactorLoginView):
    """
    aaactl's login wizard.

    Subclasses django_security_keys.ext.two_factor.views.LoginView so we get
    the passkey + TOTP + backup-code step flow for free.

    The three policy properties below are read by the base class to decide
    which wizard steps to show. They resolve to the OR-union of the user's
    org policies; the cache lives on the view instance so condition_dict's
    repeated step-predicate evaluations don't requery the DB.
    """

    def get_org_auth_settings(self) -> dict:
        """
        Return the effective MFA policy for the wizard's current user as the
        OR-union of every org they belong to: any org that enables a
        restriction is enough to enforce it.

        Cached on the view instance because the base class checks the three
        policy flags multiple times per request (condition_dict, has_*_step,
        done()). Returns an empty dict — without populating the cache — until
        the auth step has produced a user, so the eventual real policy isn't
        shadowed by a stale empty result.

        Keys match the property contract of
        django_security_keys.ext.two_factor.views.LoginView:
        ``disable_password_auth``, ``disable_totp``, ``require_passkey_mfa``.
        """
        if hasattr(self, "_org_auth_settings_cache"):
            return self._org_auth_settings_cache
        user = self.get_user()
        if not user or not user.is_authenticated:
            return {}
        policy = effective_mfa_policy(user)
        self._org_auth_settings_cache = {
            "disable_password_auth": policy["disable_password"],
            "disable_totp": policy["disable_totp"],
            "require_passkey_mfa": policy["require_passkey_mfa"],
        }
        return self._org_auth_settings_cache

    @property
    def disable_password_auth(self) -> bool:
        return self.get_org_auth_settings().get("disable_password_auth", False)

    @property
    def disable_totp(self) -> bool:
        return self.get_org_auth_settings().get("disable_totp", False)

    @property
    def require_passkey_mfa(self) -> bool:
        return self.get_org_auth_settings().get("require_passkey_mfa", False)

    def _orgs_enforcing(self, attr: str) -> list[str]:
        return orgs_enforcing(self.get_user(), attr)

    def get_passkey_required_error(self) -> str:
        # str() because gettext_lazy returns a proxy that the session JSON
        # serializer can't handle.
        orgs = self._orgs_enforcing("disable_password")
        if orgs:
            return str(
                _(
                    "%(orgs)s requires passkey authentication. "
                    "Please log in with a passkey."
                )
                % {"orgs": ", ".join(orgs)}
            )
        return str(
            _(
                "Your organization requires passkey authentication. "
                "Please log in with a passkey."
            )
        )

    def get_mfa_incomplete_redirect(self):
        user = self.get_user()
        passkey_path = bool(self.storage.data.get("passkey_authenticated"))

        if self.disable_totp and user.totpdevice_set.exists():
            # TOTP enrolled but forbidden by policy — must enroll a different
            # method. Shared with ProfileView so the wording stays identical
            # across the first landing and later EnforceMFA bounces.
            msg = mfa_setup_required_message(user, effective_mfa_policy(user))
        elif passkey_path:
            # Passkey login succeeded but org requires a 2nd factor and the
            # user has none enrolled.
            orgs = self._orgs_enforcing("require_passkey_mfa")
            msg = str(
                _(
                    "%(orgs)s requires MFA after passkey authentication. "
                    "Please set up an MFA method to proceed."
                )
                % {"orgs": ", ".join(orgs) or _("Your organization")}
            )
        else:
            # Password path + disable_totp but no TOTP device anyway —
            # nothing is being bypassed at the wizard level. If the user's
            # policy also sets require_passkey_mfa, EnforceMFA is the
            # load-bearing safeguard: it redirects them to /two_factor/profile/
            # on their next request.
            return None

        self.request.session["passkey_mfa_error"] = msg
        self.request.session["mfa_setup_required"] = True
        return reverse("two_factor:profile")

    def done(self, form_list, **kwargs):
        # Library done() may redirect into the wizard for the disable_password_auth
        # block or the MFA-incomplete lock-in. Honour those redirects so we don't
        # blow past them with our success URL — otherwise EnforceMFA has to catch
        # the user on the next request, which is an extra hop and a fragile invariant.
        response = super().done(form_list, **kwargs)
        if isinstance(response, HttpResponseRedirect) and (
            "/two_factor/" in response.url or "/account/login/" in response.url
        ):
            return response
        if not getattr(getattr(self.request, "user", None), "is_authenticated", False):
            return response
        path = self.request.POST.get("next") or self.request.GET.get("next")
        target = valid_redirect(path, get_fallback_url(self.request.user))
        return redirect(target) if target else response

    def get_context_data(self, form, **kwargs):
        context = super().get_context_data(form, **kwargs)
        context.update(_branding_context(self.request))
        # The library populates passkey_error for in-request failures (e.g.
        # attempt_passkey_auth raised). When the library's done() rejects a
        # password under disable_password_auth, it stashes the message in
        # session under passkey_required_error and redirects back here —
        # pull it into the same context key so one template alert covers both.
        if not context.get("passkey_error"):
            context["passkey_error"] = self.request.session.pop(
                "passkey_required_error", None
            )
        return context

    def get_form_kwargs(self, step=None):
        kwargs = super().get_form_kwargs(step=step)

        if step == "security-key":
            kwargs.update(
                {
                    "device": self.get_security_key_device(),
                    "request": self.request,
                    "passkey_credential_id": self.storage.data.get(
                        "passkey_credential_id"
                    ),
                }
            )

        return kwargs

    def get(self, *args, **kwargs):
        # If the user is already authenticated, skip the wizard and send
        # them home — except when an OAuth /authorize/ flow has bounced them
        # here, in which case they need the wizard to confirm.
        if self.request.user.is_authenticated:
            next_path = urlparse(self.request.GET.get("next", "")).path
            authorize_path = reverse("oauth2_provider:authorize")
            if not next_path.startswith(authorize_path):
                return redirect(get_fallback_url(self.request.user))
        return super().get(*args, **kwargs)


class ProfileView(BaseProfileView):
    """
    aaactl's MFA management page. Subclasses two_factor.views.ProfileView to
    explain why the user is here: either a specific message stashed by
    LoginView mid-login, or — for users bounced here by EnforceMFA, which
    sets no message — a policy-derived one computed from their current state.
    """

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        msg = self.request.session.pop("passkey_mfa_error", None)
        if not msg:
            policy = effective_mfa_policy(user)
            # A user is held on this page either by the mfa_setup_required
            # marker or by require_passkey_mfa; show a reason for both so every
            # forced landing is explained.
            locked_in = (
                self.request.session.get("mfa_setup_required")
                or policy["require_passkey_mfa"]
            )
            if locked_in and not user_has_satisfying_2fa(user, policy):
                msg = mfa_setup_required_message(user, policy)
        context["passkey_mfa_error"] = msg
        return context


def _backup_tokens_reauth_fresh(request) -> bool:
    ts = request.session.get(settings.BACKUP_TOKENS_REAUTH_SESSION_KEY)
    if not isinstance(ts, (int, float)):
        return False
    return (time.time() - ts) < settings.BACKUP_TOKENS_REAUTH_TTL


class BackupTokensView(BaseBackupTokensView):
    """
    aaactl's backup-token management.

    Require an out-of-band reauthentication before the codes can be viewed or
    regenerated. BackupTokensConfirmView handles the proof step (TOTP code,
    existing backup code, or WebAuthn assertion) and stamps the session with
    a timestamp on success. Every request here checks that timestamp against
    settings.BACKUP_TOKENS_REAUTH_TTL — stale or missing -> redirect to
    confirm. The check covers both GET (view existing codes) and POST
    (regenerate), so accidentally landing on this URL never leaks codes, and
    the regen form is a simple safety checkbox — no reauth inputs and no
    copy-pasting the codes visible above it.

    The upstream BackupTokensView class is wrapped with otp_required
    (two_factor/views/core.py:637), which gates on request.user.is_verified()
    — a session-wide flag set by django-otp at login. Our reauth-marker is a
    stronger, action-specific gate: it requires a fresh challenge of any
    accepted type (TOTP, backup code, or WebAuthn). is_verified() also reads
    False for passkey-authenticated sessions (django-otp doesn't track
    WebAuthn), so falling through to otp_required would incorrectly block
    users who just proved identity at our confirm view. Skip it by calling
    FormView.dispatch directly instead of super().dispatch.
    """

    form_class = account.forms.BackupTokensRegenForm

    @method_decorator([never_cache, login_required])
    def dispatch(self, request, *args, **kwargs):
        if not _backup_tokens_reauth_fresh(request):
            return redirect("two_factor:backup_tokens_confirm")
        return FormView.dispatch(self, request, *args, **kwargs)


class BackupTokensConfirmView(FormView):
    """
    Reauthentication step that gates BackupTokensView. Renders the reauth
    form (TOTP code, backup code, or WebAuthn assertion) on a page that
    deliberately does not display any of the user's backup codes — so the
    "existing backup code" reauth path can't be defeated by copy-pasting
    from the same screen. On success, stamps the session with the current
    time and bounces the user to the backup-tokens listing page.
    """

    form_class = account.forms.BackupTokensReauthForm
    template_name = "two_factor/core/backup_tokens_confirm.html"

    @method_decorator([never_cache, login_required])
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["request"] = self.request
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        self.request.session[settings.BACKUP_TOKENS_REAUTH_SESSION_KEY] = time.time()
        return redirect("two_factor:backup_tokens")


class DisableView(BaseDisableView):
    """
    Clear the backup-tokens reauth marker once 2FA is disabled. Defense in
    depth: any elevated-access state from before the device removal should
    not outlive it. The lib's DisableView performs its own fresh reauth, so
    the user has already proved identity here — we just don't want a stale
    /backup/tokens/ marker carrying that elevation forward into the next
    visit.
    """

    def form_valid(self, form):
        response = super().form_valid(form)
        self.request.session.pop(settings.BACKUP_TOKENS_REAUTH_SESSION_KEY, None)
        return response


class SetupView(BaseSetupView):
    """
    aaactl's MFA enrollment wizard. Subclasses two_factor.views.SetupView to:
      1. Block setup until the user's email is confirmed.
      2. Filter the TOTP (generator) method when org policy disables TOTP, so
         users in such orgs can only enrol non-TOTP methods.
      3. Clear the post-passkey lock-in marker (mfa_setup_required) once setup
         completes, freeing the user from EnforceMFA's redirect loop.
    """

    def post(self, request, *args, **kwargs):
        email_confirmed = getattr(
            getattr(request.user, "user_settings", None),
            "email_confirmed",
            False,
        )
        if not email_confirmed:
            messages.error(
                request,
                _("Please confirm your email address before enabling MFA."),
            )
            return redirect("two_factor:profile")
        return super().post(request, *args, **kwargs)

    def get_available_methods(self):
        methods = super().get_available_methods()
        if self.request.user.is_authenticated:
            policy = effective_mfa_policy(self.request.user)
            if policy.get("disable_totp"):
                methods = [m for m in methods if m.code != "generator"]
        return methods

    def done(self, form_list, **kwargs):
        self.request.session.pop("mfa_setup_required", None)
        return super().done(form_list, **kwargs)


def get_jwt_tokens(user):
    """
    Generate JWT tokens for the given user.

    Returns a dictionary containing the refresh and access tokens as strings.
    """
    refresh = RefreshToken.for_user(user)

    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


def valid_frontend_redirect(path, fallback, user):
    """
    Validates the redirect path to a frontend service and returns a valid redirect URL
    or the fallback URL if the redirect path is invalid.
    """
    if not path:
        return fallback

    original_next = path

    parts = urlparse(path)
    origin = f"{parts.scheme}://{parts.netloc}"
    if origin not in settings.FRONTEND_ORIGINS:
        return fallback

    tokens = get_jwt_tokens(user)
    parts = parts._replace(path=f'/login/{tokens.get("refresh")}/?next={original_next}')

    return parts.geturl()


def login_frontend(request):
    """
    View function for handling frontend login.
    Will redirect to the frontend service with a JWT refresh token if the user is authenticated.
    """
    env = {}
    show_register_link = getattr(settings, "SHOW_REGISTER_LINK", True)

    if request.user.is_authenticated:
        redirect_next = valid_frontend_redirect(
            request.GET.get("next"), reverse("account:controlpanel"), request.user
        )

        # redirect_next is already cleaned and validated
        # through valid_frontend_redirect at this point
        return HttpResponseRedirect(redirect_next)

    if request.method == "POST":
        form = account.forms.Login(data=request.POST)
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data["username_or_email"],
                password=form.cleaned_data["password"],
            )

            if user is not None:
                # JWT-issuing path cannot drive an MFA wizard. If org policy
                # disallows password-only login or requires a 2nd factor,
                # 401 with mfa_required so the SPA can route to /two_factor/login/.
                policy = effective_mfa_policy(user)
                if policy["disable_password"] or policy["require_passkey_mfa"]:
                    return JsonResponse(
                        {
                            "detail": "MFA required",
                            "mfa_required": True,
                            "policy": policy,
                            "wizard_url": reverse("two_factor:login"),
                        },
                        status=401,
                    )

                fn_login(request, user)
                redirect_next = valid_frontend_redirect(
                    request.POST.get("next"), reverse("account:controlpanel"), user
                )

                # redirect_next is already cleaned and validated
                # through valid_frontend_redirect at this point
                return HttpResponseRedirect(redirect_next)
            else:
                messages.error(
                    request, _("Login failed: Wrong username / email / password")
                )

    else:
        form = account.forms.Login()

    env.update(
        login_form=form,
        password_login_enabled=settings.PASSWORD_LOGIN_ENABLED,
        login_form_action="account:auth-login-frontend",
        show_register_link=show_register_link,
    )

    return render(request, "account/auth/login.html", env)


def logout(request):
    fn_logout(request)

    response = redirect(reverse("account:auth-login"))

    # loop through all services and unset session cookies
    for svc in Service.objects.all():
        # invlaidate coookies with name {service_slug}sid on response
        response.delete_cookie(f"{svc.slug}sid")

    return response


def register(request):
    env = {}
    org_branding = {}
    branding_org = getattr(settings, "BRANDING_ORG", None)
    has_invite_secret = request.GET.get("invite")
    http_host = request.get_host()
    org_branding_components = {}
    invite = None

    if has_invite_secret:
        try:
            invite = Invitation.objects.get(secret=has_invite_secret)
            env.update(invite=invite)
        except Invitation.DoesNotExist:
            messages.error(request, _("Invitation not found"))
            return redirect("/")

    # we only allow registration if the setting is enabled or an invite is present
    if not settings.ENABLE_ACCOUNT_REGISTRATION and not invite:
        # registration is disabled, return a 404
        raise Http404

    show_captcha = getattr(settings, "RECAPTCHA_PUBLIC_KEY", None) and getattr(
        settings, "RECAPTCHA_SECRET_KEY", None
    )

    if request.method == "POST":
        form = account.forms.RegisterUser(data=request.POST, show_captcha=show_captcha)
        if form.is_valid():
            try:
                del form.cleaned_data["password_confirmation"]
                if show_captcha:
                    del form.cleaned_data["captcha"]
                user = get_user_model().objects.create_user(**form.cleaned_data)
                fn_login(request, user, backend="django_grainy.backends.GrainyBackend")
                redirect_next = valid_redirect(
                    request.POST.get("next"), reverse("account:controlpanel")
                )

                return redirect(redirect_next)
            except Exception as exc:
                messages.error(request, _("Registration error: {}").format(exc))

    else:
        form = account.forms.RegisterUser(show_captcha=show_captcha)

        # if invitation we can set the email field
        if invite:
            form.fields["email"].initial = invite.email

    if branding_org:
        org_branding = OrganizationBranding.objects.filter(
            org__slug=branding_org
        ).first()
    elif http_host:
        org_branding = OrganizationBranding.objects.filter(http_host=http_host).first()

    if org_branding:
        name = org_branding.org.name
        org_branding_components = {
            "name": name,
            "html_footer": org_branding.html_footer,
            "css": org_branding.css,
            "dark_logo_url": format_logo_url(org_branding.dark_logo_url),
            "light_logo_url": format_logo_url(org_branding.light_logo_url),
            "favicon_url": format_logo_url(org_branding.favicon_url),
            "custom_org": True,
        }

    env.update(
        register_form=form,
        password_login_enabled=settings.PASSWORD_LOGIN_ENABLED,
        org_branding=org_branding_components,
        show_captcha=show_captcha,
    )

    return render(request, "account/auth/register.html", env)


def start_reset_password(request):
    form = account.forms.StartPasswordReset()
    env = {"form": form}
    return render(request, "account/auth/reset-password.html", env)


def reset_password(request, secret):
    try:
        password_reset = PasswordReset.objects.get(secret=secret)
    except PasswordReset.DoesNotExist:
        messages.error(_("Password reset session not found"))
        return redirect("/")

    form = account.forms.PasswordReset(initial={"secret": secret})
    env = {"password_reset": password_reset, "form": form}

    return render(request, "account/auth/reset-password.html", env)


def accept_invite(request, secret):
    try:
        invite = Invitation.objects.get(secret=secret)
    except Invitation.DoesNotExist:
        messages.error(request, _("Invitation not found"))
        return redirect("/")

    if invite.expired:
        messages.error(request, _("The invite has expired"))
        return redirect("/")

    if not request.user.is_authenticated:
        return redirect(
            reverse("account:auth-login")
            + f"?next={request.get_full_path()}&invite={secret}"
        )

    invite.complete(request.user)
    messages.info(request, _("You have joined {}").format(invite.org.label))

    set_selected_org(request, invite.org)

    if invite.service:
        return redirect(invite.service.service_url.format(org=invite.org))
    else:
        return redirect("/")


@login_required
def confirm_email(request, secret):
    try:
        email_confirmation = EmailConfirmation.objects.get(secret=secret)
    except EmailConfirmation.DoesNotExist:
        messages.error(request, _("Email confirmation process not found"))
        return redirect("/")

    if email_confirmation.email != request.user.email:
        messages.error(
            request,
            _(
                "The email of the user currenty logged in does not match the email linked to the email confirmation process"
            ),
        )
        return redirect("/")

    email_confirmation.complete()
    messages.success(request, _("Email address confirmed!"))

    return redirect("/")


oauth_profile_scopes = ["profile", "api_keys", "provider:peeringdb"]


# @protected_resource(scopes=oauth_profile_scopes)
def oauth_profile(request):
    from account.rest.serializers import Serializers

    user = request.user

    oauth = get_oauthlib_core()

    oauth_email, _ = oauth.verify_request(request, scopes=["email"])
    oauth_api_keys, _ = oauth.verify_request(request, scopes=["api_keys"])

    oauth_provider_passthru = []

    for social_auth in user.social_auth.all():
        key = f"provider:{social_auth.provider}"
        verify, _ = oauth.verify_request(request, scopes=[key])
        if verify:
            oauth_provider_passthru.append(social_auth)

    json_params = {}

    if "pretty" in request.GET:
        json_params.update(indent=2)

    data = dict(
        id=user.id,
        user_name=user.username,
        given_name=user.first_name,
        family_name=user.last_name,
        is_superuser=user.is_superuser,
        is_staff=user.is_staff,
        name=f"{user.first_name} {user.last_name}",
        # TODO: dont assume oauth implies verification
        verified_user=True,
        organizations=[
            Serializers.org(instance=org.org, context={"user": user}).data
            for org in user.org_user_set.all()
        ],
    )

    if oauth_email:
        data.update(dict(email=user.email))

    for social_auth in oauth_provider_passthru:
        provider = social_auth.provider
        data[provider] = social_auth.extra_data
        if "access_token" in data[provider]:
            del data[provider]["access_token"]
        if "token_type" in data[provider]:
            del data[provider]["token_type"]

    return JsonResponse(data, json_dumps_params=json_params)
