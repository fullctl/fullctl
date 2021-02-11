# from django.conf import settings
# from django.http import Http404, HttpResponse
from django.shortcuts import redirect

from fullctl.django.decorators import require_auth


@require_auth()
def org_redirect(request):
    return redirect(f"/{request.org.slug}/")
