"""Tests for the whitelisted-env endpoint and its serialization helpers."""

import importlib
import sys

import pytest
from django.test import override_settings
from django.urls import clear_url_caches, reverse

from fullctl.django.rest.views.env import (
    _assign_path,
    _build_env,
    _normalize_service_bridge_ref,
)

# --- Pure function tests --------------------------------------------------


class TestNormalizeServiceBridgeRef:
    def test_normalizes_class_path_to_service_name(self):
        assert (
            _normalize_service_bridge_ref("fullctl.service_bridge.nautobot.Device")
            == "nautobot"
        )
        assert (
            _normalize_service_bridge_ref("fullctl.service_bridge.pdbctl.Facility")
            == "pdbctl"
        )

    def test_empty_string_returns_empty_string(self):
        assert _normalize_service_bridge_ref("") == ""

    def test_none_returns_empty_string(self):
        assert _normalize_service_bridge_ref(None) == ""

    def test_single_segment_returned_verbatim(self):
        assert _normalize_service_bridge_ref("nautobot") == "nautobot"

    def test_two_segments_returns_second_to_last(self):
        assert _normalize_service_bridge_ref("nautobot.Device") == "nautobot"


class TestAssignPath:
    def test_single_key(self):
        out = {}
        _assign_path(out, ["device"], "nautobot")
        assert out == {"device": "nautobot"}

    def test_nested_path_creates_intermediate_dicts(self):
        out = {}
        _assign_path(out, ["sot", "device"], "nautobot")
        assert out == {"sot": {"device": "nautobot"}}

    def test_deeply_nested_path(self):
        out = {}
        _assign_path(out, ["a", "b", "c", "d"], 1)
        assert out == {"a": {"b": {"c": {"d": 1}}}}

    def test_reuses_existing_intermediate_dict(self):
        out = {"sot": {"device": "x"}}
        _assign_path(out, ["sot", "facility"], "pdbctl")
        assert out == {"sot": {"device": "x", "facility": "pdbctl"}}

    def test_scalar_at_intermediate_key_is_replaced(self):
        # Last-write-wins: deeper entry overwrites a scalar at the parent key.
        out = {"sot": "already-a-string"}
        _assign_path(out, ["sot", "device"], "nautobot")
        assert out == {"sot": {"device": "nautobot"}}


class TestBuildEnv:
    def test_empty_whitelist_returns_empty_dict(self):
        assert _build_env({}) == {}

    @override_settings(
        SERVICE_BRIDGE_REF_DEVICE="fullctl.service_bridge.nautobot.Device"
    )
    def test_service_bridge_ref_is_normalized(self):
        result = _build_env({"sot.device": "SERVICE_BRIDGE_REF_DEVICE"})
        assert result == {"sot": {"device": "nautobot"}}

    @override_settings(SERVICE_BRIDGE_REF_DEVICE="")
    def test_unset_service_bridge_ref_is_empty_string(self):
        result = _build_env({"sot.device": "SERVICE_BRIDGE_REF_DEVICE"})
        assert result == {"sot": {"device": ""}}

    def test_missing_setting_returns_empty_string(self):
        result = _build_env({"foo.bar": "NO_SUCH_SETTING"})
        assert result == {"foo": {"bar": ""}}

    @override_settings(SOME_STRING_SETTING="hello", SERVICE_BRIDGE_REF_DEVICE="")
    def test_non_bridge_setting_passes_through_verbatim(self):
        # Non-SERVICE_BRIDGE_REF_ values pass through without normalization.
        result = _build_env(
            {
                "misc.greeting": "SOME_STRING_SETTING",
                "sot.device": "SERVICE_BRIDGE_REF_DEVICE",
            }
        )
        assert result == {
            "misc": {"greeting": "hello"},
            "sot": {"device": ""},
        }

    @override_settings(
        SERVICE_BRIDGE_REF_DEVICE="fullctl.service_bridge.nautobot.Device",
        SERVICE_BRIDGE_REF_FACILITY="fullctl.service_bridge.pdbctl.Facility",
    )
    def test_multiple_bridge_keys_share_parent(self):
        result = _build_env(
            {
                "sot.device": "SERVICE_BRIDGE_REF_DEVICE",
                "sot.facility": "SERVICE_BRIDGE_REF_FACILITY",
            }
        )
        assert result == {
            "sot": {"device": "nautobot", "facility": "pdbctl"},
        }


# --- Endpoint integration tests ------------------------------------------

# grainy_endpoint requires `service.<SERVICE_TAG>.<permission_id>` = "r" in
# addition to org-level access; test SERVICE_TAG is "fullctl".


def _grant_service_read(user, org):
    user.grainy_permissions.add_permission_set(
        {f"service.fullctl.{org.permission_id}": "r"}
    )


@override_settings(API_ENV_WHITELIST={"sot.device": "SERVICE_BRIDGE_REF_DEVICE"})
@override_settings(SERVICE_BRIDGE_REF_DEVICE="fullctl.service_bridge.nautobot.Device")
def test_env_endpoint_returns_normalized_whitelist(db, dj_account_objects):
    _grant_service_read(dj_account_objects.user, dj_account_objects.org)
    client = dj_account_objects.api_client

    response = client.get(
        reverse(
            "fullctl_env_api:env-list", kwargs={"org_tag": dj_account_objects.org.slug}
        )
    )

    assert response.status_code == 200
    payload = response.json()
    # Fullctl JSONRenderer wraps single objects in `data: [...]`.
    assert payload["data"] == [{"sot": {"device": "nautobot"}}]
    assert payload["errors"] == {}


@override_settings(API_ENV_WHITELIST={"sot.device": "SERVICE_BRIDGE_REF_DEVICE"})
@override_settings(SERVICE_BRIDGE_REF_DEVICE="")
def test_env_endpoint_returns_empty_string_when_sot_unset(db, dj_account_objects):
    _grant_service_read(dj_account_objects.user, dj_account_objects.org)
    client = dj_account_objects.api_client

    response = client.get(
        reverse(
            "fullctl_env_api:env-list", kwargs={"org_tag": dj_account_objects.org.slug}
        )
    )

    assert response.status_code == 200
    assert response.json()["data"] == [{"sot": {"device": ""}}]


@override_settings(API_ENV_WHITELIST={})
def test_env_endpoint_empty_whitelist_returns_empty_object(db, dj_account_objects):
    _grant_service_read(dj_account_objects.user, dj_account_objects.org)
    client = dj_account_objects.api_client

    response = client.get(
        reverse(
            "fullctl_env_api:env-list", kwargs={"org_tag": dj_account_objects.org.slug}
        )
    )

    assert response.status_code == 200
    assert response.json()["data"] == [{}]


@override_settings(API_ENV_WHITELIST={"sot.device": "SERVICE_BRIDGE_REF_DEVICE"})
def test_env_endpoint_returns_403_without_service_permission(db, dj_account_objects):
    # Org-level "crud" alone is not enough — the service perm must also be set.
    client = dj_account_objects.api_client

    response = client.get(
        reverse(
            "fullctl_env_api:env-list", kwargs={"org_tag": dj_account_objects.org.slug}
        )
    )

    assert response.status_code == 403


@override_settings(API_ENV_WHITELIST={"sot.device": "SERVICE_BRIDGE_REF_DEVICE"})
def test_env_endpoint_requires_authentication(db, dj_client_anon, dj_account_objects):
    response = dj_client_anon.get(
        reverse(
            "fullctl_env_api:env-list", kwargs={"org_tag": dj_account_objects.org.slug}
        )
    )

    # Grainy may 403 unauth requests instead of 401; both are "access denied".
    assert response.status_code in (401, 403)


@override_settings(API_ENV_WHITELIST={"sot.device": "SERVICE_BRIDGE_REF_DEVICE"})
def test_env_endpoint_unknown_org_returns_404(db, dj_account_objects):
    _grant_service_read(dj_account_objects.user, dj_account_objects.org)
    client = dj_account_objects.api_client

    # RequestAugmentation 404s on an unknown org_tag before the view runs.
    response = client.get(
        reverse("fullctl_env_api:env-list", kwargs={"org_tag": "does-not-exist"})
    )

    assert response.status_code == 404


def test_apidocs_schema_generates_with_env_registered(db, dj_client_anon):
    # Env must be a plain ViewSet (no serializer_class) so OpenAPI schema
    # generation doesn't raise. The test project declares API_ENV_WHITELIST,
    # so the env route is registered and walked here. Regresses the crash a
    # GenericViewSet caused on /apidocs/schema.json.
    response = dj_client_anon.get(reverse("api_schema"))

    assert response.status_code == 200
    assert "/api/env/{org_tag}/" in response.json()["paths"]


def test_env_url_not_registered_without_whitelist(settings):
    """A service that doesn't declare API_ENV_WHITELIST must not expose /api/env/."""
    saved = settings.API_ENV_WHITELIST
    del settings.API_ENV_WHITELIST

    try:
        sys.modules.pop("fullctl.django.urls", None)
        clear_url_caches()
        mod = importlib.import_module("fullctl.django.urls")

        namespaces = {
            getattr(pattern, "namespace", None) for pattern in mod.urlpatterns
        }
        assert "fullctl_env_api" not in namespaces
    finally:
        # Restore setting before reload so subsequent tests get the URL back.
        settings.API_ENV_WHITELIST = saved
        sys.modules.pop("fullctl.django.urls", None)
        clear_url_caches()
        importlib.import_module("fullctl.django.urls")
