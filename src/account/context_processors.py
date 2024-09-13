from django.conf import settings


def permissions(request):
    context = {}

    try:
        instances = [request.selected_org]
    except AttributeError:
        return {"permissions": context}
    ops = [("c", "create"), ("r", "read"), ("u", "update"), ("d", "delete")]

    for instance in instances:
        if not instance:
            continue
        for namespace in instance.permission_namespaces:
            for op, name in ops:
                key = "{}_{}_{}".format(
                    name,
                    instance.HandleRef.tag,
                    namespace.replace(".{org_id}", "").replace(".", "__"),
                )
                context[key] = request.perms.check(
                    namespace.format(org_id=instance.id), op, ignore_grant_all=True
                )

    context["has_asn"] = request.perms.check("verified.asn.?", "r")

    return {"permissions": context}


def info(request):
    user_has_org_setup = False

    # `user` may not necessarily be set on the request object
    # We're currently not 100% sure when this happens and have
    # had no success reproducing this issue at will.
    # For now, treat the symptom
    # TODO: When does this happen?
    if hasattr(request, "user") and request.user.is_authenticated:
        user_has_org_setup = request.user.org_user_set.filter(
            org__user__isnull=True
        ).exists()
    return {
        "billing_env": settings.BILLING_ENV,
        "release_env": settings.RELEASE_ENV,
        "version": settings.PACKAGE_VERSION,
        "server_email": settings.SERVER_EMAIL,
        "google_analytics_id": settings.GOOGLE_ANALYTICS_ID,
        "cloudflare_analytics_id": settings.CLOUDFLARE_ANALYTICS_ID,
        "enable_email_confirmation": settings.ENABLE_EMAIL_CONFIRMATION,
        "has_org_setup": user_has_org_setup,
        "PDB_OAUTH_PROMPT_LINK": settings.PDB_OAUTH_PROMPT_LINK,
    }
