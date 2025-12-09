from django.conf import settings
from django.http import Http404
from django.shortcuts import redirect, render
from fullctl.django.decorators import load_instance, require_auth

from django_devicectl.models.devicectl import Facility

# Create your views here.


def make_env(request, **kwargs):
    r = {"env": settings.RELEASE_ENV, "version": settings.PACKAGE_VERSION}

    r["sot"] = {
        "device": settings.SERVICE_BRIDGE_REF_DEVICE,
    }

    r.update(**kwargs)
    return r


@require_auth()
@load_instance()
def view_instance(request, instance, **kwargs):
    env = make_env(request, instance=instance, org=instance.org)
    return render(request, "theme-select.html", env)


@require_auth()
@load_instance()
def view_instance_load_facility(request, instance, facility_tag, **kwargs):
    try:
        facility = Facility.objects.get(instance=instance, slug=facility_tag)
    except Facility.DoesNotExist:
        raise Http404

    env = make_env(request, instance=instance, org=instance.org)
    env["select_facility"] = facility

    return render(request, "theme-select.html", env)


@require_auth()
def org_redirect(request):
    return redirect(f"/{request.org.slug}/")
