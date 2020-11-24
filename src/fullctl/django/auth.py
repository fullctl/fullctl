from django.conf import settings

import django_grainy.util
import django_grainy.remote


class Permissions(django_grainy.util.Permissions):
    pass


class RemotePermissions(django_grainy.remote.Permissions):

    """
    Permissions are provided from the oauth instance.

    We use grainy remote permissions to facilitate this
    """

    def __init__(self, obj):
        super().__init__(obj, **settings.GRAINY_REMOTE)

    def prepare_request(self, params, headers):
        try:
            key = self.obj.key_set.first().key
            headers.update(Authorization=f"Bearer {key}")
        except AttributeError:
            pass


def permissions(user, refresh=False):
    if hasattr(user, "_fullctl_permissions") and not refresh:
        return user._fullctl_permissions
    perms = RemotePermissions(user)
    user._fullctl_permissions = perms
    return perms
