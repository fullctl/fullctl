from django.http import Http404, HttpResponse
from django.conf import settings
from django.shortcuts import render, redirect

from fullctl.django.decorators import (
    require_auth,
)

@require_auth()
def org_redirect(request):
    return redirect(f"/{request.org.slug}/")
