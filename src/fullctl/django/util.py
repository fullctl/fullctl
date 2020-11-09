from django.conf import settings
import django_peeringdb.models.concrete as pdb_models
from fullctl.django.auth import permissions
from fullctl.django.models import (
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
