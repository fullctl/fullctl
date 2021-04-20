# from django.conf import settings
from django.http import Http404, HttpResponse
from django.shortcuts import redirect
from django.utils.safestring import mark_safe

from fullctl.django.decorators import require_auth


@require_auth()
def org_redirect(request):
    return redirect(f"/{request.org.slug}/")


def diag(request):
    if not request.user.is_superuser:
        raise Http404()

    return HttpResponse(mark_safe(f"<div>{request.META}</div>"))
