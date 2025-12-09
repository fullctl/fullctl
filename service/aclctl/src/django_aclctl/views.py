from django.conf import settings
from django.http import Http404
from django.shortcuts import redirect, render
from fullctl.django.decorators import load_instance, require_auth

from django_aclctl.models import AccessControlList

# Create your views here.


def make_env(request, **kwargs):
    r = {"env": settings.RELEASE_ENV, "version": settings.PACKAGE_VERSION}
    r.update(**kwargs)

    return r


@require_auth()
@load_instance()
def view_instance(request, instance, **kwargs):
    env = make_env(request, instance=instance, org=instance.org)
    return render(request, "theme-select.html", env)


@require_auth()
@load_instance()
def view_instance_load_acl(request, instance, acl_tag, **kwargs):
    try:
        access_control_list = AccessControlList.objects.get(
            instance=instance, slug=acl_tag
        )
    except AccessControlList.DoesNotExist:
        raise Http404

    env = make_env(request, instance=instance, org=instance.org)
    env["select_access_control_list"] = access_control_list

    return render(request, "theme-select.html", env)


@require_auth()
def org_redirect(request):
    return redirect(f"/{request.org.slug}/")
