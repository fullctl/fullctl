from django.conf import settings


def account_service(request):

    context = {}

    # TODO abstract so other auth services can be
    # defined
    context.update(
        account_service={
            "urls": {
                "billing_setup": f"{settings.OAUTH_TWENTYC_HOST}/billing/setup?org={request.org.slug}",
                "create_org": f"{settings.OAUTH_TWENTYC_HOST}/account/org/create/",
                "manage_org": f"{settings.OAUTH_TWENTYC_HOST}/account/?org={request.org.slug}",
            },
        },
        # TODO: deprecated
        oauth_manages_org=True,
        service_logo_dark=f"{settings.SERVICE_TAG}/logo-darkbg.svg",
        service_logo_light=f"{settings.SERVICE_TAG}/logo-lightbg.svg",
        service_tag=settings.SERVICE_TAG,
        service_name=settings.SERVICE_TAG.replace("ctl", ""),
    )

    return context


def permissions(request):
    context = {}

    ops = [("c", "create"), ("r", "read"), ("u", "update"), ("d", "delete")]

    is_accessible = request.org in request.org.accessible(request.user)

    for op, name in ops:
        key = f"{name}_instance"
        if name == "read":
            context[key] = is_accessible
        else:
            context[key] = request.perms.check(request.org, op)

    return {"permissions": context}
