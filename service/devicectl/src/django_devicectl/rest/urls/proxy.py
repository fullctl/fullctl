from django.conf import settings
from fullctl.django.rest.urls.proxy import proxy_api, setup

PROXY_HOST = getattr(settings, "DEVICECTL_PROXY", None)
ENDPOINTS = getattr(
    settings,
    "DEVICECTL_PROXY_ENDPOINTS",
    [
        "device",
        "phyport",
        "virtport",
        "logport",
    ],
)

if PROXY_HOST:
    setup("devicectl", proxy_api("devicectl", PROXY_HOST, ENDPOINTS))
