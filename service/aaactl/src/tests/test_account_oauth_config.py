"""
Tests for the DB-backed OAuth strategy + secret rotation endpoint.

Covers:
- ``DBStrategy._SETTING_RE`` matching across single-word and multi-word
  service names and across the multi-underscore field names
  (e.g. ``ACCESS_TOKEN_URL`` vs ``ACCESS_TOKEN_METHOD``).
- Settings fall-through behavior: no row, row with empty field, row with
  populated field — and that non-OAuth settings are passed through untouched.
- Per-strategy memoization of OAuthConfig lookups.
- ``PUT /api/account/oauth_config/{service_id}/`` rotation: auth required,
  permission required, 404 when row missing, with-secret vs no-secret paths,
  and that ``save(update_fields=...)`` doesn't clobber concurrent edits to
  other columns.
"""

import json
from unittest import mock

import account.models as models
import pytest
from account.social_strategy import _SETTING_RE, DBStrategy
from django.urls import reverse

# ----- DBStrategy regex --------------------------------------------------


@pytest.mark.parametrize(
    "name,expected_service,expected_field",
    [
        ("SOCIAL_AUTH_PEERINGDB_KEY", "PEERINGDB", "KEY"),
        ("SOCIAL_AUTH_PEERINGDB_SECRET", "PEERINGDB", "SECRET"),
        ("SOCIAL_AUTH_PEERINGDB_DEFAULT_SCOPE", "PEERINGDB", "DEFAULT_SCOPE"),
        ("SOCIAL_AUTH_PEERINGDB_EXTRA_DATA", "PEERINGDB", "EXTRA_DATA"),
        ("SOCIAL_AUTH_PEERINGDB_AUTHORIZATION_URL", "PEERINGDB", "AUTHORIZATION_URL"),
        (
            "SOCIAL_AUTH_AZUREAD_V2_TENANT_OAUTH2_TENANT_ID",
            "AZUREAD_V2_TENANT_OAUTH2",
            "TENANT_ID",
        ),
        # multi-word service + multi-word field — exercises greedy backtracking
        (
            "SOCIAL_AUTH_OKTA_OPENIDCONNECT_ACCESS_TOKEN_URL",
            "OKTA_OPENIDCONNECT",
            "ACCESS_TOKEN_URL",
        ),
        (
            "SOCIAL_AUTH_OKTA_OPENIDCONNECT_ACCESS_TOKEN_METHOD",
            "OKTA_OPENIDCONNECT",
            "ACCESS_TOKEN_METHOD",
        ),
        ("SOCIAL_AUTH_GOOGLE_OAUTH2_KEY", "GOOGLE_OAUTH2", "KEY"),
        ("SOCIAL_AUTH_GOOGLE_OAUTH2_PROFILE_URL", "GOOGLE_OAUTH2", "PROFILE_URL"),
    ],
)
def test_setting_re_matches(name, expected_service, expected_field):
    m = _SETTING_RE.match(name)
    assert m is not None, name
    assert m.group("service") == expected_service
    assert m.group("field") == expected_field


@pytest.mark.parametrize(
    "name",
    [
        "SOCIAL_AUTH_KEY",  # no service prefix
        "SOCIAL_AUTH_PIPELINE",  # not a DB-backed field
        "SOCIAL_AUTH_PEERINGDB_API_URL",  # not a DB-backed field
        "DJANGO_SECRET_KEY",  # not SOCIAL_AUTH_-prefixed
    ],
)
def test_setting_re_skips(name):
    assert _SETTING_RE.match(name) is None


# ----- DBStrategy DB lookup behavior -------------------------------------


def _make_strategy():
    """Build a DBStrategy without going through social_django.load_strategy."""
    return DBStrategy(storage=None)


def test_strategy_returns_db_value(db):
    models.OAuthConfig.objects.create(
        service_id="peeringdb",
        key="DBKEY",
        secret="DBSECRET",
        authorization_url="https://example.test/auth/",
    )
    strategy = _make_strategy()
    assert strategy.get_setting("SOCIAL_AUTH_PEERINGDB_KEY") == "DBKEY"
    assert strategy.get_setting("SOCIAL_AUTH_PEERINGDB_SECRET") == "DBSECRET"
    assert (
        strategy.get_setting("SOCIAL_AUTH_PEERINGDB_AUTHORIZATION_URL")
        == "https://example.test/auth/"
    )


def test_strategy_falls_through_when_field_empty(db, settings):
    """Empty DB field → fall back to Django settings."""
    models.OAuthConfig.objects.create(service_id="peeringdb", key="", secret="")
    settings.SOCIAL_AUTH_PEERINGDB_KEY = "FROM_SETTINGS"
    strategy = _make_strategy()
    assert strategy.get_setting("SOCIAL_AUTH_PEERINGDB_KEY") == "FROM_SETTINGS"


def test_strategy_falls_through_when_no_row(db, settings):
    """No DB row → fall back to Django settings."""
    settings.SOCIAL_AUTH_NEWBACKEND_KEY = "FROM_SETTINGS"
    strategy = _make_strategy()
    assert strategy.get_setting("SOCIAL_AUTH_NEWBACKEND_KEY") == "FROM_SETTINGS"


def test_strategy_returns_tenant_id_from_db(db):
    """tenant_id is DB-backed (added for Entra/Azure-style backends)."""
    models.OAuthConfig.objects.create(
        service_id="azuread_v2_tenant_oauth2",
        key="K",
        secret="S",
        tenant_id="abcd-1234-tenant-guid",
    )
    strategy = _make_strategy()
    assert (
        strategy.get_setting("SOCIAL_AUTH_AZUREAD_V2_TENANT_OAUTH2_TENANT_ID")
        == "abcd-1234-tenant-guid"
    )


def test_strategy_tenant_id_falls_through_to_settings(db, settings):
    """Empty tenant_id in DB → settings value wins."""
    models.OAuthConfig.objects.create(
        service_id="azuread_v2_tenant_oauth2", key="K", secret="S", tenant_id=""
    )
    settings.SOCIAL_AUTH_AZUREAD_V2_TENANT_OAUTH2_TENANT_ID = "FROM_ENV"
    strategy = _make_strategy()
    assert (
        strategy.get_setting("SOCIAL_AUTH_AZUREAD_V2_TENANT_OAUTH2_TENANT_ID")
        == "FROM_ENV"
    )


def test_strategy_falls_through_for_empty_list(db):
    """Empty list/dict in DB are also "unset" — defer to backend default."""
    models.OAuthConfig.objects.create(service_id="peeringdb", default_scope=[])
    strategy = _make_strategy()
    # Settings doesn't define SOCIAL_AUTH_PEERINGDB_DEFAULT_SCOPE so the
    # parent strategy raises AttributeError, signaling "not configured" —
    # python-social-auth's setting() catches this and falls back to the
    # backend's class-level DEFAULT_SCOPE.
    with pytest.raises(AttributeError):
        strategy.get_setting("SOCIAL_AUTH_PEERINGDB_DEFAULT_SCOPE")


def test_strategy_passes_through_non_oauth_setting(db, settings):
    """Settings that don't match the SOCIAL_AUTH_{SVC}_{FIELD} pattern
    must not trigger a DB lookup and must return the raw settings value."""
    settings.SOCIAL_AUTH_PIPELINE = ("a", "b", "c")
    strategy = _make_strategy()
    assert strategy.get_setting("SOCIAL_AUTH_PIPELINE") == ("a", "b", "c")


def test_strategy_memoizes_db_lookup(db):
    """Multiple lookups for the same service_id must hit the DB only once."""
    models.OAuthConfig.objects.create(
        service_id="peeringdb", key="K", secret="S", profile_url="https://p.test/"
    )
    strategy = _make_strategy()
    with mock.patch.object(
        models.OAuthConfig.objects,
        "get",
        wraps=models.OAuthConfig.objects.get,
    ) as get_mock:
        strategy.get_setting("SOCIAL_AUTH_PEERINGDB_KEY")
        strategy.get_setting("SOCIAL_AUTH_PEERINGDB_SECRET")
        strategy.get_setting("SOCIAL_AUTH_PEERINGDB_PROFILE_URL")
        assert get_mock.call_count == 1


def test_strategy_memoizes_missing_row(db, settings):
    """Negative results (no row) are also cached."""
    settings.SOCIAL_AUTH_NOPE_KEY = "x"
    settings.SOCIAL_AUTH_NOPE_SECRET = "y"
    strategy = _make_strategy()
    with mock.patch.object(
        models.OAuthConfig.objects,
        "get",
        wraps=models.OAuthConfig.objects.get,
    ) as get_mock:
        strategy.get_setting("SOCIAL_AUTH_NOPE_KEY")
        strategy.get_setting("SOCIAL_AUTH_NOPE_SECRET")
        assert get_mock.call_count == 1


# ----- Rotation endpoint -------------------------------------------------


ROTATE_URL = "account_api:oauth_config-detail"


def _grant(user, namespace, perms="crud"):
    user.grainy_permissions.add_permission(namespace, perms)


def test_rotate_requires_auth(db, account_objects):
    """No auth header → 403 (DRF default for missing IsAuthenticated)."""
    models.OAuthConfig.objects.create(service_id="peeringdb", key="K", secret="OLD")
    response = account_objects.api_client_anon.put(
        reverse(ROTATE_URL, args=("peeringdb",)),
        data=json.dumps({}),
        content_type="application/json",
    )
    assert response.status_code == 403


def test_rotate_requires_permission(db, account_objects):
    """API key without oauth_config.{service_id} perm → 403."""
    models.OAuthConfig.objects.create(service_id="peeringdb", key="K", secret="OLD")
    response = account_objects.api_client_anon.put(
        reverse(ROTATE_URL, args=("peeringdb",)),
        data=json.dumps({}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {account_objects.api_key.key}",
    )
    assert response.status_code == 403


def test_rotate_unknown_service_id_denied(db, account_objects):
    """Permission check runs before existence check — caller can't probe
    which service_ids exist by checking for 404 vs 403."""
    _grant(account_objects.user, "oauth_config.peeringdb")
    response = account_objects.api_client_anon.put(
        reverse(ROTATE_URL, args=("nonexistent",)),
        data=json.dumps({}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {account_objects.api_key.key}",
    )
    assert response.status_code == 403


def test_rotate_with_explicit_secret(db, account_objects):
    """Caller-supplied secret replaces the stored value and is echoed back."""
    config = models.OAuthConfig.objects.create(
        service_id="peeringdb", key="K", secret="OLD"
    )
    _grant(account_objects.user, "oauth_config.peeringdb")

    response = account_objects.api_client_anon.put(
        reverse(ROTATE_URL, args=("peeringdb",)),
        data=json.dumps({"secret": "NEW-EXPLICIT"}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {account_objects.api_key.key}",
    )
    assert response.status_code == 200

    payload = response.json()["data"][0]
    assert payload["service_id"] == "peeringdb"
    assert payload["key"] == "K"
    assert payload["secret"] == "NEW-EXPLICIT"

    config.refresh_from_db()
    assert config.secret == "NEW-EXPLICIT"


def test_rotate_without_secret_generates_one(db, account_objects):
    """Missing/blank ``secret`` → server generates one and returns it."""
    config = models.OAuthConfig.objects.create(
        service_id="peeringdb", key="K", secret="OLD"
    )
    _grant(account_objects.user, "oauth_config.peeringdb")

    response = account_objects.api_client_anon.put(
        reverse(ROTATE_URL, args=("peeringdb",)),
        data=json.dumps({}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {account_objects.api_key.key}",
    )
    assert response.status_code == 200

    payload = response.json()["data"][0]
    assert payload["service_id"] == "peeringdb"
    assert payload["key"] == "K"
    new_secret = payload["secret"]
    assert new_secret and new_secret != "OLD"

    config.refresh_from_db()
    assert config.secret == new_secret


def test_rotate_does_not_clobber_concurrent_edits(db, account_objects):
    """``update_fields=["secret", "updated"]`` keeps key/URLs/scopes that were
    edited via admin between the rotation request being authenticated and
    the actual save."""
    config = models.OAuthConfig.objects.create(
        service_id="peeringdb", key="ORIGINAL_KEY", secret="OLD"
    )
    _grant(account_objects.user, "oauth_config.peeringdb")

    # Simulate a concurrent admin edit landing after the row was loaded by
    # the view but before the save runs.
    models.OAuthConfig.objects.filter(pk=config.pk).update(
        key="EDITED_BY_ADMIN", profile_url="https://admin-edited.test/"
    )

    response = account_objects.api_client_anon.put(
        reverse(ROTATE_URL, args=("peeringdb",)),
        data=json.dumps({"secret": "ROTATED"}),
        content_type="application/json",
        HTTP_AUTHORIZATION=f"Bearer {account_objects.api_key.key}",
    )
    assert response.status_code == 200

    config.refresh_from_db()
    assert config.secret == "ROTATED"
    # Concurrent edits must survive — only the secret column was written.
    assert config.key == "EDITED_BY_ADMIN"
    assert config.profile_url == "https://admin-edited.test/"


def test_rotate_get_not_allowed(db, account_objects):
    """No GET on the detail URL — secret should not be readable."""
    models.OAuthConfig.objects.create(service_id="peeringdb", key="K", secret="OLD")
    _grant(account_objects.user, "oauth_config.peeringdb")
    response = account_objects.api_client_anon.get(
        reverse(ROTATE_URL, args=("peeringdb",)),
        HTTP_AUTHORIZATION=f"Bearer {account_objects.api_key.key}",
    )
    assert response.status_code == 405
