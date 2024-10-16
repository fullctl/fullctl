import fullctl.service_bridge.aaactl as aaactl
from django.conf import settings

from django_ixctl.models.ixctl import InternetExchange

def check_trial_available(org_slug, ix_slug):
    try:
        ix = InternetExchange.objects.get(instance__org__slug=org_slug, slug=ix_slug)
    except InternetExchange.DoesNotExist:
        return {"trial_available": False}

    service = aaactl.ServiceApplication()

    return {
        "trial_available": service.trial_available(
            org_slug, settings.SERVICE_TAG, ix.id
        ),
        "trial_object": ix,
    }


def trial_available(request):
    """
    Returns a boolean indicating whether or not there is a trial
    available for the requesting organization at the service
    """

    # retrieve ix_tag from request url parse information

    try:
        ix_tag = request.resolver_match.kwargs.get("ix_tag")
    except AttributeError:
        ix_tag = None

    if ix_tag is None:
        return {"trial_available": False}

    return check_trial_available(request.org.slug, ix_tag)

def ixctl_settings(request):

    return {
        "MEMBER_CASE_NUMBERS_ENABLED": settings.MEMBER_CASE_NUMBERS_ENABLED,
        "PORT_QUANTITIES": [i for i in range(1, settings.PORT_LIMIT + 1)],
    }