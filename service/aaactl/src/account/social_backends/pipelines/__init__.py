import social_core.pipeline.user

from account.models import UserPermissionOverride, UserSettings


def get_username(strategy, details, backend, user=None, *args, **kwargs):
    if "username" in details:
        details["username"] = details["username"].lower()

    return social_core.pipeline.user.get_username(
        strategy, details, backend, user=user, *args, **kwargs
    )


def _sync_peeringdb_verified_asns(user, networks):
    """
    Takes a user and a dictionary of peeringdb networks as they are
    returned from peeringdb oauth and sets up verified.asn
    permissions accordingly
    """

    namespaces = []

    for network in networks:
        asn = network["asn"]
        perms = network["perms"]
        namespace = f"verified.asn.{asn}.peeringdb"

        try:
            override = user.permission_overrides.get(namespace=namespace)
            override.permissions = perms
            override.save()
        except UserPermissionOverride.DoesNotExist:
            override = UserPermissionOverride.objects.create(
                user=user, namespace=namespace, permissions=perms
            )

        override.apply()

        namespaces.append(namespace)

    # delete old overrides

    user.permission_overrides.filter(
        namespace__regex=r"^verified\.asn\.\d+\.peeringdb$"
    ).exclude(namespace__in=namespaces).delete()

    # delete old permissions

    user.grainy_permissions.filter(
        namespace__regex=r"^verified\.asn\.\d+\.peeringdb$"
    ).exclude(namespace__in=namespaces).delete()


def sync_peeringdb(backend, details, response, uid, user, *args, **kwargs):
    if backend.name != "peeringdb":
        return

    social = kwargs.get("social") or backend.strategy.storage.user.get_social_auth(
        backend.name, uid
    )

    if social:
        social.extra_data["email"] = details["email"]
        social.save()
        networks = social.extra_data.get("networks") or []

        _sync_peeringdb_verified_asns(user, networks)


def auto_confirm_email(backend, details, response, uid, user, *args, **kwargs):
    if user.email and user.email == details.get("email"):
        user_settings, _ = UserSettings.objects.get_or_create(user=user)
        user_settings.email_confirmed = True
        user_settings.save()
