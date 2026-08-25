from django.conf import settings
from rest_framework import viewsets
from rest_framework.response import Response

from fullctl.django.rest.decorators import grainy_endpoint
from fullctl.django.rest.route.env import route


@route
# Plain ViewSet (no serializer_class); GenericViewSet would break /apidocs schema gen.
class Env(viewsets.ViewSet):
    """
    Exposes a whitelist of runtime settings to the frontend so an SPA can
    branch behavior on values that would otherwise live only in Django
    templates (e.g. the `sot.device` flag used to switch between the
    create-new and attach-existing device flows).

    Each service opts in by declaring `settings.API_ENV_WHITELIST`, a mapping
    of dotted-output-path -> Django settings name. Example:

        API_ENV_WHITELIST = {
            "sot.device": "SERVICE_BRIDGE_REF_DEVICE",
        }

    yields a response like:

        {"sot": {"device": "nautobot"}}

    SERVICE_BRIDGE_REF_* class paths are normalized to just the service name
    (e.g. "fullctl.service_bridge.nautobot.Device" -> "nautobot"); an unset
    setting yields an empty string, which the FE can treat as falsy.
    """

    ref_tag = "env"

    # Uses the default `org.{permission_id}` namespace — any user with read
    # access to the org (established by RequestAugmentation middleware from
    # the org_tag URL segment) can query env. The whitelist itself is the
    # security boundary; no per-key permissioning.
    @grainy_endpoint()
    def list(self, request, *args, **kwargs):
        whitelist = getattr(settings, "API_ENV_WHITELIST", {}) or {}
        return Response(_build_env(whitelist))


def _build_env(whitelist):
    out = {}
    for path, setting_name in whitelist.items():
        raw = getattr(settings, setting_name, "")
        value = (
            _normalize_service_bridge_ref(raw)
            if setting_name.startswith("SERVICE_BRIDGE_REF_")
            else raw
        )
        _assign_path(out, path.split("."), value)
    return out


def _assign_path(obj, keys, value):
    cur = obj
    for k in keys[:-1]:
        nxt = cur.get(k)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[k] = nxt
        cur = nxt
    cur[keys[-1]] = value


def _normalize_service_bridge_ref(class_path):
    """
    "fullctl.service_bridge.nautobot.Device" -> "nautobot"
    "" / None -> ""
    """
    if not class_path:
        return ""
    parts = str(class_path).split(".")
    return parts[-2] if len(parts) >= 2 else str(class_path)
