import django.http
from django.shortcuts import redirect
from django.urls import reverse

from fullctl.django.models import Instance, Organization


class require_auth:

    """
    decorate a view to require auth
    """

    def __call__(self, fn):
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:

                # return redirect(
                #     reverse("social:begin", args=("twentyc",))
                #     + f"?next={request.get_full_path()}"
                # )
                return redirect(reverse("login") + f"?next={request.get_full_path()}")

            return fn(request, *args, **kwargs)

        wrapped.__name__ = fn.__name__
        return wrapped


class load_instance:

    """
    decorator that loads the instance for the selected
    org.

    org is selected in middleware.py and set on the request
    at request.org

    This will create the org's instance if it does not exist yet

    Keyword Argument(s):

    - public (`bool`): if public, no permission checks will be done,
    otherwise read permission to the org is required
    """

    def __init__(self, public=False):
        self.model = Instance
        self.public = public

    def __call__(self, fn):
        model = self.model
        public = self.public

        def wrapped(request, *args, **kwargs):

            org = request.org
            print("ORG", org)
            if not public and org not in Organization.accessible(request.user):
                raise django.http.Http404()

            try:
                instance, _ = model.objects.get_or_create(org=org)
            except model.DoesNotExist:
                raise django.http.Http404()

            request.app_id = instance.app_id

            return fn(request, instance, *args, **kwargs)

        wrapped.__name__ = fn.__name__
        wrapped.public = public

        return wrapped
