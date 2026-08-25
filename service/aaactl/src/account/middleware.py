from account.impersonate import is_impersonating
from account.models import (
    Organization,
    effective_mfa_policy,
    user_has_satisfying_2fa,
)
from account.session import set_selected_org
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.translation import gettext as _
from django_grainy.util import Permissions
from social_core.exceptions import AuthFailed
from social_django.middleware import SocialAuthExceptionMiddleware


class OrgGone(KeyError):
    """
    Raised when the org set in the user's request session is no longer available
    to the user.
    """

    pass


class RequestAugmentation:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def set_selected_org(self, request):
        org_slug = request.GET.get("org")
        if org_slug == "personal":
            set_selected_org(request, request.user.personal_org)
        elif org_slug:
            try:
                org = Organization.objects.get(slug=org_slug)
                set_selected_org(request, org, raise_on_denial=True)
            except Organization.DoesNotExist:
                pass
            except PermissionError:
                messages.error(
                    request,
                    _(
                        "You do not have the permissions to perform this action in {}"
                    ).format(org.label),
                )

        try:
            request.session["selected_org"]
            org = Organization.objects.get(id=request.session["selected_org"])
            if not org.org_user_set.filter(user=request.user).exists():
                raise OrgGone()
        except (Organization.DoesNotExist, OrgGone):
            org = Organization.default_org(request.user)
            set_selected_org(request, org)
        except KeyError:
            org = set_selected_org(request)

        if not request.perms.check(org, "r"):
            org = set_selected_org(request)

        request.selected_org = org

    def process_view(self, request, view_func, view_args, view_kwargs):
        request.perms = Permissions(request.user)
        self.set_selected_org(request)


class Impersonation:
    """
    Handles impersonation logic

    Should be added after auth middleware
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        user = is_impersonating(request)
        if user:
            response.headers["X-User"] = user.id

        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = is_impersonating(request)

        # cache impersonation on request and set the request user
        # to the user being impersonated
        if user:
            request.impersonating = request.user.impersonating

            # never impersonate in django-admin
            if request.path.startswith("/admin/"):
                return

            # never impersonate during oauth
            if request.path.startswith("/account/auth/o/"):
                return

            # finalize impersonation by setting the request user
            request.user = user


class OAuthLoginError(SocialAuthExceptionMiddleware):
    """
    Graceful handling of some OAuth login errors (instead of scary 500 internal error page)

    - PeeringDB user is not verified
    """

    def get_redirect_uri(self, request, exception):
        if isinstance(exception, AuthFailed):
            if "PeeringDB user is not verified" in str(exception):
                return request.build_absolute_uri("/")
        return super().get_redirect_uri(request, exception)


class EnforceMFA:
    """
    Enforce per-org MFA policy after authentication by pinning users to
    /two_factor/profile/ until they enroll a device satisfying the policy.

    1. Post-passkey lock-in: honours the "mfa_setup_required" session marker
       set by LoginView when a passkey login can't satisfy require_passkey_mfa.
    2. Always-on: also redirects any logged-in user whose policy demands MFA
       but has no satisfying device, catching flags flipped mid-session.
    """

    # URL names whose paths must be excluded from the redirect-loop. Resolved
    # via reverse() on first use so urls.py stays the single source of truth —
    # rename or remount a route and this list follows automatically. The bare
    # "/security-keys/" prefix is hardcoded because it's a third-party mount.
    _EXCLUDED_URL_NAMES = (
        "two_factor:login",
        "two_factor:profile",
        "account:auth-login",
        "account:auth-logout",
        "account:auth-register",
        "account:auth-reset-password-start",
    )
    _EXTRA_PREFIXES = ("/security-keys/", "/jsi18n/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.process_request(request)
        if response is not None:
            return response
        return self.get_response(request)

    @classmethod
    def _excluded_prefixes(cls) -> tuple[str, ...]:
        # Lazy because reverse() needs the URL conf loaded — eager evaluation
        # at module import would risk an import cycle.
        if not hasattr(cls, "_prefix_cache"):
            cls._prefix_cache = (
                tuple(reverse(n) for n in cls._EXCLUDED_URL_NAMES) + cls._EXTRA_PREFIXES
            )
        return cls._prefix_cache

    @classmethod
    def is_path_excluded(cls, path: str) -> bool:
        if settings.STATIC_URL and path.startswith(settings.STATIC_URL):
            return True
        if settings.MEDIA_URL and path.startswith(settings.MEDIA_URL):
            return True
        return any(path.startswith(p) for p in cls._excluded_prefixes())

    def process_request(self, request):
        user = request.user
        if not user.is_authenticated:
            return None

        email_confirmed = getattr(
            getattr(user, "user_settings", None),
            "email_confirmed",
            False,
        )
        if not email_confirmed:
            return None

        policy = effective_mfa_policy(user)

        # 1) post-passkey lock-in
        if request.session.get("mfa_setup_required"):
            if user_has_satisfying_2fa(user, policy):
                request.session.pop("mfa_setup_required", None)
            elif not self.is_path_excluded(request.path):
                return redirect(reverse("two_factor:profile"))
            else:
                return None

        # 2) always-on require_passkey_mfa enforcement
        if policy["require_passkey_mfa"] and not user_has_satisfying_2fa(user, policy):
            if not self.is_path_excluded(request.path):
                return redirect(reverse("two_factor:profile"))

        return None
