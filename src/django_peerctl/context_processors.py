from django.conf import settings


def conf(request):
    """
    add some commonly used setting variables to all template
    contexts
    """
    return {
        "settings": {
            "emails": {
                "noreply": settings.NO_REPLY_EMAIL,
                "support": settings.SUPPORT_EMAIL,
                "peer_request_from": settings.PEER_REQUEST_FROM_EMAIL,
            },
            "peeringdb": {
                "url": settings.PEERINGDB_URL,
                "source_of_truth": settings.PDBCTL_SOT_IX,
            },
            "default_page": settings.DEFAULT_PAGE,
            # defined in aaactl, used globally
            "PDB_OAUTH_PROMPT_LINK": settings.PDB_OAUTH_PROMPT_LINK,
        },
    }


def permissions(request):
    """
    add some commonly used permission variables to all template
    contexts
    """

    if not hasattr(request, "org"):
        # org is not set on request, this happens during display
        # of error handling while the account is not authenticated
        #
        # if org is not set, there are no permissions
        # to scope so just assume no permissions
        return {"peerctl_permissions": {}}

    namespace = f"service.devicectl.{request.org.permission_id}"
    rv = {
        "peerctl_permissions": {
            "device_management": request.perms.check(namespace, "r"),
        },
    }
    return rv
