from django.utils.translation import gettext_lazy as _

IXF_MEMBER_TYPE = (
    ("peering", _("peering")),
    ("ixp", _("ixp")),
    ("routeserver", _("routeserver")),
    ("probono", _("probono")),
)

PORT_STATE = (
    ("ok", _("Active")),
    ("awaiting_cross_connect", _("Awaiting cross connect")),
    ("provisioning", _("Provisioning")),
    ("suspended", _("Suspended")),
    ("pending_deletion", _("Pending deletion")),
    ("admin_down", _("Admin down")),
    ("down", _("Down")),
)

ARS_TYPES = (
    ("bird", _("Bird")),
    ("bird2", _("Bird 2")),
    ("openbgpd", _("OpenBGPD")),
)

ARS_NO_EXPORT_ACTIONS = (
    ("pass", _("Pass (Treat as transitive)")),
    ("strip", _("Strip (Treat as non-transitive)")),
)

PERMISSION_REQUEST_TYPES = (("net_ix", _("Manage network at exchange")),)

IXF_EXPORT_PRIVACY_TYPES = (
    ("public", _("IX-F export feed is public")),
    ("private", _("IX-F export feed requires secret key to view")),
)

OPERATIONAL_STATUS_CHOICES = (
    ("operational", _("Operational")),
    ("maintenance", _("Maintenance")),
    ("down", _("Down")),
)

PORT_CONFIG_INTENT = (
    (None, _("No operation")),
    ("create", _("Create")),
    ("resize", _("Resize")),
    ("lag-increase", _("Increase LAG quantity")),
    ("lag-decrease", _("Decrease LAG quantity")),
)
