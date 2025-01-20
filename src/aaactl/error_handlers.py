import datetime
import sys

from django.conf import settings
from django.shortcuts import render

import whitelabel_fullctl.models as branding_models


def handle_error(request, exception, status):
    if exception:
        request.error_response = exception
        exc_type = exception.__class__
    else:
        exc_type, exception, tb = sys.exc_info()

    request.error_response = exception

    context = {
        "error": {
            "status": status,
            "type_description": f"{exc_type}",
            "description": f"{exception}",
            "path": request.path,
            "ip_address": request.META.get("HTTP_X_FORWARDED_FOR"),
            "referer": request.META.get("HTTP_REFERER"),
            "timestamp": datetime.datetime.utcnow(),
        },
        "org_branding": {},
    }

    branding_org = getattr(settings, "BRANDING_ORG", None)
    if branding_org:
        org_branding = branding_models.OrganizationBranding.objects.filter(
            org__slug=branding_org
        ).first()
        if not org_branding:
            if http_host := request.get_host():
                org_branding = branding_models.OrganizationBranding.objects.filter(
                    http_host=http_host
                ).first()

        if org_branding:
            context["org_branding"] = {
                "name": org_branding.org.name,
                "html_footer": org_branding.html_footer,
                "css": org_branding.css,
                "dark_logo_url": org_branding.dark_logo_url,
                "light_logo_url": org_branding.light_logo_url,
                "favicon_url": org_branding.favicon_url,
                "custom_org": True,
            }

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
