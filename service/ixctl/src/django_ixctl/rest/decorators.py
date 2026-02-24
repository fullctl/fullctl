import django.http
import django_ixctl.models as models
from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse

from fullctl.django.models import Instance, Organization
from fullctl.django.rest.decorators import grainy_endpoint as _grainy_endpoint


class grainy_endpoint(_grainy_endpoint):
    def __init__(self, *args, **kwargs):
        super().__init__(
            instance_class=models.Instance,
            explicit=kwargs.pop("explicit", False),
            *args,
            **kwargs,
        )
        if "namespace" not in kwargs:
            self.namespace += ["ixctl"]


def validate_public_view_ix_and_instance(request, kwargs):
    try:
        instance = Instance.objects.get(org=request.org)
    except Instance.DoesNotExist:
        raise django.http.Http404()

    try:
        ix = models.InternetExchange.objects.get(
            instance=instance, slug=kwargs["ix_tag"], public_view=True
        )
    except models.InternetExchange.DoesNotExist:
        return None, None

    return ix, instance


class require_auth_ix:
    """
    decorate a view to require auth
    """

    def __call__(self, fn):
        def wrapped(request, *args, **kwargs):
            local_auth = getattr(settings, "USE_LOCAL_PERMISSIONS", False)
            public_view_internet_exchange = None

            if not request.user.is_authenticated:
                if not local_auth:
                    (
                        public_view_internet_exchange,
                        _,
                    ) = validate_public_view_ix_and_instance(request, kwargs)
                    if public_view_internet_exchange:
                        return fn(request, *args, **kwargs)

                    return redirect(
                        reverse("social:begin", args=("twentyc",))
                        + f"?next={request.get_full_path()}"
                    )
                else:
                    (
                        public_view_internet_exchange,
                        _,
                    ) = validate_public_view_ix_and_instance(request, kwargs)
                    if public_view_internet_exchange:
                        return fn(request, *args, **kwargs)

                    return redirect(
                        reverse("admin:login") + f"?next={request.get_full_path()}"
                    )

            return fn(request, *args, **kwargs)

        wrapped.__name__ = fn.__name__
        return wrapped


class load_instance_ix:
    """
    decorator that loads the instance for the selected
    org for ixctl.

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
            if not public and org not in Organization.accessible(request.user):
                public_view_internet_exchange = None

                if request.user.is_authenticated and not getattr(
                    request, "impersonating", None
                ):
                    raise django.http.Http404()
                else:
                    (
                        public_view_internet_exchange,
                        instance,
                    ) = validate_public_view_ix_and_instance(request, kwargs)
                    if public_view_internet_exchange:
                        return fn(request, instance, *args, **kwargs)

                    return redirect(
                        reverse("login") + f"?next={request.get_full_path()}"
                    )

            try:
                instance, _ = model.objects.get_or_create(org=org)
            except model.DoesNotExist:
                raise django.http.Http404()

            request.app_id = instance.app_id

            return fn(request, instance, *args, **kwargs)

        wrapped.__name__ = fn.__name__
        wrapped.public = public

        return wrapped
