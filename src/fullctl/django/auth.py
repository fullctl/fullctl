import json
import requests

import django_grainy.remote
import django_grainy.util
from django.db import transaction
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from social_django.models import UserSocialAuth

from fullctl.django.context import current_request

import fullctl.django.models.concrete.account as account_models

import fullctl.service_bridge.aaactl as aaactl


class RemotePermissionsError(IOError):
    def __init__(self):

        if not getattr(settings, "SERVICE_KEY", None):
            msg = "No SERVICE_KEY specified"
        else:
            msg = (
                "Could not parse response from aaactl for remote permissions."
                "Please check aaactl logs for diagnostic details"
            )
        super().__init__(msg)


class Permissions(django_grainy.util.Permissions):
    pass


def require_user(aaactl_user_id):

    """
    Fetches and syncs a user from aaactl using the service bridge
    """

    user = get_user_model().objects.filter(social_auth__uid=aaactl_user_id).first()

    if not user:

        aaactl_user = aaactl.User().object(aaactl_user_id)

        user = get_user_model().objects.create_user(
            username = aaactl_user.username,
            first_name = aaactl_user.first_name,
            last_name = aaactl_user.last_name,
            is_staff = aaactl_user.is_staff,
            is_superuser = aaactl_user.is_superuser,
            email = aaactl_user.email
        )

        account_models.Organization.sync(aaactl_user.organizations, user, backend="twentyc")

        UserSocialAuth.objects.create(
            user = user,
            provider = "twentyc",
            extra_data = {},
            uid = aaactl_user_id,
        )

    return user


class RemotePermissions(django_grainy.remote.Permissions):

    """
    Permissions are provided from the oauth instance.

    We use grainy remote permissions to facilitate this
    """

    def __init__(self, obj):
        super().__init__(obj, **settings.GRAINY_REMOTE)


    @transaction.atomic
    def handle_impersonation(self, response):

        user_id = response.headers.get("X-User")

        print("IMPERSONATE", user_id, response.headers)

        if not user_id:
            return

        user = require_user(user_id)

        print("IMPERSONATE", user)

        with current_request() as request:

            if not request.user.is_superuser:
                return

            request.impersonating = {
                "superuser": request.user,
                "user": user
            }
            request.user = user

    def fetch(self, url, cache_key, **params):
        try:

            if self.cache > 0:
                cached = cache.get(cache_key)
                if cached:
                    return json.loads(cached)

            headers = {}
            self.prepare_request(params, headers)
            response = requests.get(url, params=params, headers=headers)

            self.handle_impersonation(response)

            data = response.json()

            if self.cache > 0:
                cache.set(cache_key, json.dumps(data), self.cache)

            return data

        except json.decoder.JSONDecodeError:
            raise RemotePermissionsError()

    def prepare_request(self, params, headers):
        try:
            if isinstance(self.obj, get_user_model()):
                key = settings.SERVICE_KEY
                headers.update(Grainy=self.obj.social_auth.first().uid)
            else:
                key = self.obj.key

            headers.update(Authorization=f"Bearer {key}")
        except AttributeError:
            pass


def permissions(permission_holder, refresh=False):
    if hasattr(permission_holder, "_fullctl_permissions") and not refresh:
        return permission_holder._fullctl_permissions

    if getattr(settings, "USE_LOCAL_PERMISSIONS", False):
        perms = Permissions(permission_holder)
    else:
        perms = RemotePermissions(permission_holder)
    permission_holder._fullctl_permissions = perms
    return perms
