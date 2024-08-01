"""
If PeeringDB is not the SoT for exchange members and network presences
Then we cannot use pdb to autocomplete network searches.

A dynamic switch needs to happen if settings.PDBCTL_SOT_IX = False
"""
from django.conf import settings
from dal import autocomplete

import fullctl.service_bridge.ixctl as ixctl

from fullctl.django.autocomplete.pdb import peeringdb_net

class ixctl_net(autocomplete.Select2QuerySetView):

    """
    Network autocompletion from ixctl

    Returns list of networks with presences at SoT exchanges
    in the ixctl service bridge
    """

    def get_queryset(self):
        qs = list(ixctl.InternetExchangeMember().objects(
            q=self.q,
            distinct="asn",
            sot=True
        ))
        return qs

    def get_result_label(self, item):
        return f"AS{item.asn} {item.name}"

    def get_result_value(self, item):
        return item.asn


def net_autocomplete_view() -> autocomplete.Select2QuerySetView:
    """
    Return the appropriate network autocomplete view based on
    the settings.PDBCTL_SOT_IX value
    """
    if settings.PDBCTL_SOT_IX:
        return peeringdb_net
    return ixctl_net