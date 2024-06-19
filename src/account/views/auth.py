from urllib.parse import urlparse

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth import login as fn_login
from django.contrib.auth import logout as fn_logout
from django.contrib.auth.decorators import login_required
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.urls import resolve, reverse
from django.utils.translation import gettext as _
from oauth2_provider.oauth2_backends import get_oauthlib_core
from rest_framework_simplejwt.tokens import RefreshToken

import account.forms
from account.models import EmailConfirmation, Invitation, PasswordReset
from account.session import set_selected_org
from applications.models import Service
from whitelabel_fullctl.models import OrganizationBranding

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


def login(request):
    env = {}
    org_branding = {}
    branding_org = getattr(settings, "BRANDING_ORG", None)
    show_register_link = getattr(settings, "ENABLE_ACCOUNT_REGISTRATION", True)
    http_host = request.get_host()
    org_branding_components = {}

    if request.user.is_authenticated:
        messages.info(request, _("Already logged in"))
        return redirect(reverse("account:controlpanel"))

    if request.method == "POST":
        form = account.forms.Login(data=request.POST)
        redirect_next = valid_redirect(
            request.POST.get("next"), reverse("account:controlpanel")
        )
        if form.is_valid():
            user = authenticate(
                request,
                username=form.cleaned_data["username_or_email"],
                password=form.cleaned_data["password"],
            )

            if user is not None:
                fn_login(request, user)

                # redirect_next is alraedy cleaned and validated
                # through valid_redirect at this point
                return redirect(redirect_next)  # lgtm[py/url-redirection]
            else:
                messages.error(
                    request, _("Login failed: Wrong username / email / password")
                )

    else:
        form = account.forms.Login()

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
            "dark_logo_url": org_branding.dark_logo_url,
            "light_logo_url": org_branding.light_logo_url,
            "custom_org": True,
        }

    env.update(
        login_form=form,
        password_login_enabled=settings.PASSWORD_LOGIN_ENABLED,
        org_branding=org_branding_components,
        show_register_link=show_register_link,
    )

    return render(request, "account/auth/login.html", env)


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

    parts = urlparse(path)
    origin = f"{parts.scheme}://{parts.netloc}"
    if origin not in settings.FRONTEND_ORIGINS:
        return fallback

    tokens = get_jwt_tokens(user)
    parts = parts._replace(path=f'/login/{tokens.get("refresh")}/')

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
    http_host = request.get_host()
    org_branding_components = {}

    if not settings.ENABLE_ACCOUNT_REGISTRATION:
        # registration is disabled, return a 404
        raise Http404

    if request.method == "POST":
        form = account.forms.RegisterUser(data=request.POST)
        if form.is_valid():
            try:
                del form.cleaned_data["password_confirmation"]
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
        form = account.forms.RegisterUser()

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
            "dark_logo_url": org_branding.dark_logo_url,
            "light_logo_url": org_branding.light_logo_url,
            "custom_org": True,
        }

    env.update(
        register_form=form,
        password_login_enabled=settings.PASSWORD_LOGIN_ENABLED,
        org_branding=org_branding_components,
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
            reverse("account:auth-login") + f"?next={request.get_full_path()}"
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
