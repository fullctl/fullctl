from django.conf import settings
from django.shortcuts import redirect, render
from fullctl.django.decorators import load_instance, require_auth

# Create your views here.


def make_env(request, **kwargs):
    org = kwargs.get("org")
    r = {"env": settings.RELEASE_ENV, "version": settings.PACKAGE_VERSION}
    r.update(**kwargs)

    return r


@require_auth()
@load_instance()
def view_instance(request, instance, **kwargs):
    env = make_env(request, instance=instance, org=instance.org)
    return render(request, "aclctl/index.html", env)


@require_auth()
def org_redirect(request):
    return redirect(f"/{request.org.slug}/")
