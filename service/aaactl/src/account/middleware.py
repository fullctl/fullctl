from django.contrib import messages
from django.utils.translation import gettext as _
from django_grainy.util import Permissions
from social_core.exceptions import AuthFailed
from social_django.middleware import SocialAuthExceptionMiddleware

from account.impersonate import is_impersonating
from account.models import Organization
from account.session import set_selected_org


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
