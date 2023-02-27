from django.conf import settings
from django.shortcuts import redirect, render
from fullctl.django.decorators import load_instance, require_auth

from django_pdbctl.status import last_sync, stats

# Create your views here.


def make_env(request, **kwargs):
    r = {"env": settings.RELEASE_ENV, "version": settings.PACKAGE_VERSION}
    r.update(**kwargs)
    return r


@require_auth()
@load_instance()
def view_instance(request, instance, **kwargs):
    env = make_env(request, instance=instance, org=instance.org)
    env["forms"] = {}
    env["stats"] = stats()
    env["last_sync"] = last_sync()
    return render(request, "pdbctl/index.html", env)


@require_auth()
def org_redirect(request):
    return redirect(f"/{request.org.slug}/")
