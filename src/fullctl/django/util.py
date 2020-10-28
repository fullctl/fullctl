from django.conf import settings
import django_peeringdb.models.concrete as pdb_models
from django_fullctl.auth import permissions
from django_fullctl.models import (
    Instance,
    Organization,
    OrganizationUser,
    APIKey,
)


def verified_asns(perms):
    verified_asns = []
    for verified_asn in perms.pset.expand("verified.asn.?", explicit=True, exact=True):
        asn = verified_asn.keys[-1]
        try:
            pdb_net = pdb_models.Network.objects.get(asn=asn)
        except (ValueError, pdb_models.Network.DoesNotExist):
            pdb_net = None

        verified_asns.append({
            "asn": asn,
            "pdb_net": pdb_net
        })

    return verified_asns


def create_personal_org(user):

    if not settings.MANAGED_BY_OAUTH:

        # organizations are not managed by oauth
        # so for now we just ensure that each user
        # has a personal org

        if user.is_authenticated:

            org, _ = Organization.objects.get_or_create(
                name=f"{user.username} personal org",
                slug=user.username,
                personal=True,
            )

            instance = Instance.get_or_create(org)

            OrganizationUser.objects.create(
                org=org, user=user,
            )

            user.grainy_permissions.add_permission(f"*.{org.id}", "crud")
            return org
    return

