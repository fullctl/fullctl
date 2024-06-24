"""
Superuser user impersonation
"""

from django.contrib.auth import get_user_model
from django.contrib.auth.models import User

from account.models import Impersonation
from account.session import set_selected_org
from django_grainy.util import Permissions

def allowed_to_impersonate(user: User) -> bool:

    if not isinstance(user, User):
        # keys are currently not allowed to impersonate
        return False

    return getattr(user, "is_superuser", False) or Permissions(user).check("impersonate", "c")

def is_impersonating(request):
    """
    Returns whether or not the supplied request is currently impersonating a user

    Will return None if no impersonation is set up.

    Otherwise will return User instance for user being impersonated
    """

    if getattr(request, "impersonating", None):
        # Only superusers are ever able to impersonate anyone
        if not allowed_to_impersonate(request.impersonating.superuser):
            return None

        return request.impersonating.user
    elif not allowed_to_impersonate(request.user):
        return None

    try:
        return request.user.impersonating.user
    except Impersonation.DoesNotExist:
        return None


def start_impersonation(request, user):
    """
    start impersonating the specified user
    """

    # Only superusers are ever able to impersonate anyone
    if not allowed_to_impersonate(request.user):
        return

    # stop current personation

    stop_impersonation(request)

    if not isinstance(user, get_user_model()):
        raise TypeError(f"user needs to be of {get_user_model()} type")

    # cannot impersonate self

    if request.user == user:
        return

    # clear selected org from session
    try:
        del request.session["selected_org"]
    except KeyError:
        pass

    Impersonation.objects.create(user=user, superuser=request.user)


def stop_impersonation(request):
    """
    stop impersonating
    """

    impersonating = getattr(request, "impersonating", None)

    if not impersonating:
        return

    request.user = impersonating.superuser

    try:
        impersonating.delete()
    except Impersonation.DoesNotExist:
        pass

    request.impersonating = None

    # reset the selected organization to the user's default
    # org now that the impersonation has stopped

    set_selected_org(request, org=None)
