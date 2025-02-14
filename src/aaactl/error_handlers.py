import datetime
import sys

from django.conf import settings
from django.shortcuts import render
from fullctl.django.util import error_context, load_branding_info

import whitelabel_fullctl.models as branding_models


def fetch_branding(branding_org:str, request) -> branding_models.OrganizationBranding:
    org_branding = branding_models.OrganizationBranding.objects.filter(
        org__slug=branding_org
    ).first()
    if not org_branding:
        if http_host := request.get_host():
            org_branding = branding_models.OrganizationBranding.objects.filter(
                http_host=http_host
            ).first()

    return org_branding.serialize()


def handle_error(request, exception, status):
    context = {
        "error": error_context(status, exception, request),
        "org_branding": {},
        "is_error_page": True,
    }

    branding = load_branding_info(request, settings.BRANDING_ORG, fetch_branding)

    if branding:
        context["org_branding"] = branding

    response = render(request, f"common/errors/{status}.html", context)
    response.status_code = status
    return response


def handle_error_500(request, exception=None):
    return handle_error(request, exception, 500)


def handle_error_404(request, exception=None):
    return handle_error(request, exception, 404)


def handle_error_401(request, exception=None):
    return handle_error(request, exception, 401)


def handle_error_400(request, exception=None):
    return handle_error(request, exception, 400)


def handle_error_403(request, exception=None):
    return handle_error(request, exception, 403)
