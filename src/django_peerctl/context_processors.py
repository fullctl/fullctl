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
                "support": settings.DEFAULT_FROM_EMAIL,
                "peer_request_from": settings.PEER_REQUEST_FROM_EMAIL,
            },
            "peeringdb": {
                "url": settings.PEERINGDB_URL,
                "source_of_truth": settings.PDBCTL_SOT_IX,
            },
        },
    }

def permissions(request):
    """
    add some commonly used permission variables to all template
    contexts
    """
    namespace = f"service.devicectl.{request.org.permission_id}"
    rv = {
        "peerctl_permissions": {
            "device_management": request.perms.check(namespace, "r"),
        },
    }
    print("permissions: ", rv, namespace)

    return rv