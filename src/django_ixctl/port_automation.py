"""
Functions to help facilitate validation during port provisioning
process and port automation.
"""

import fullctl.service_bridge.pdbctl as pdbctl

from django_ixctl.models.ixctl import InternetExchange

from django_ixctl.schema import IXLanConfig


__all__ = [
    "get_ix_lan_config",
]



def get_ix_lan_config(ix: int | InternetExchange) -> IXLanConfig:
    """
    Get the IXLanConfig for a given InternetExchange object (or ID)
    """

    if isinstance(ix, int):
        ix = InternetExchange.objects.get(pk=ix)

    if not isinstance(ix, InternetExchange):
        raise ValueError("ix must be an InternetExchange object or ID")

    config = IXLanConfig(mtu=ix.mtu)

    for prefix in ix.prefixes.all():
        config.prefixes.append(str(prefix.prefix))

    if (not ix.mtu or not ix.prefixes) and ix.pdb_id:
        # attempt to get from peeringdb

        if not config.mtu:
            pdb_ixlan = pdbctl.InternetExchange().first(id=ix.pdb_id)
            if pdb_ixlan:
                config.mtu = pdb_ixlan.mtu
        
        if not config.prefixes:
            pdb_prefixes = pdbctl.IXLanPrefix().objects(ix=ix.pdb_id)
            for prefix in pdb_prefixes:
                config.prefixes.append(prefix.prefix)

    return config