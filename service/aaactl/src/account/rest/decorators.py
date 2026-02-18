from rest_framework import exceptions

from account.models import Organization


def set_org(fn):
    def wrapped(self, request, pk, *args, **kwargs):
        if pk == "personal":
            org = request.user.personal_org
        else:
            org = Organization.objects.get(slug=pk)
        kwargs["org"] = org
        return fn(self, request, pk, *args, **kwargs)

    wrapped.__name__ = fn.__name__
    return wrapped


def disable_api_key(fn):
    def wrapped(self, request, *args, **kwargs):
        if hasattr(request, "api_key"):
            raise exceptions.AuthenticationFailed(
                "API key authentication not allowed for this operation"
            )
        return fn(self, request, *args, **kwargs)

    wrapped.__name__ = fn.__name__
    return wrapped
