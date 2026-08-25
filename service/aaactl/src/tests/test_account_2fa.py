"""
Tests for the per-org MFA / passkey policy:

- bitmask round-trip + properties on Organization
- effective_mfa_policy() OR-combines flags across all of the user's orgs
- user_has_satisfying_2fa() honours the disable_totp policy
- EnforceMFA middleware redirects (and excludes) at the right times
- /api/account/org/{slug}/security/ GET + PUT
- password-path login wizard step transitions across the policy matrix
"""

import time

import pytest
from account.middleware import EnforceMFA
from account.models import (
    Organization,
    effective_mfa_policy,
    user_has_satisfying_2fa,
)
from account.views.auth import _backup_tokens_reauth_fresh
from django.conf import settings
from django.test import Client
from django.urls import reverse
from django_otp.plugins.otp_static.models import StaticDevice, StaticToken
from django_otp.plugins.otp_totp.models import TOTPDevice
from django_security_keys.models import SecurityKey

# -------- Organization bitmask --------


def test_org_flag_defaults_false(db, account_objects):
    org = account_objects.org
    assert org.org_flags == 0
    assert org.disable_password is False
    assert org.disable_totp is False
    assert org.require_passkey_mfa is False


def test_set_org_flag_round_trip(db, account_objects):
    org = account_objects.org

    org.set_org_flag(settings.ORG_FLAGS_PASSKEY_DISABLE_PASSWORD_AUTH, True)
    assert org.disable_password is True

    org.set_org_flag(settings.ORG_FLAGS_DISABLE_TOTP, True)
    assert org.disable_totp is True
    assert org.disable_password is True  # not clobbered

    org.set_org_flag(settings.ORG_FLAGS_PASSKEY_DISABLE_PASSWORD_AUTH, False)
    assert org.disable_password is False
    assert org.disable_totp is True


# -------- effective_mfa_policy --------


def test_effective_mfa_policy_no_flags(db, account_objects):
    policy = effective_mfa_policy(account_objects.user)
    assert policy == {
        "disable_password": False,
        "disable_totp": False,
        "require_passkey_mfa": False,
    }


def test_effective_mfa_policy_or_combines_across_orgs(db, account_objects):
    user = account_objects.user

    account_objects.org.set_org_flag(settings.ORG_FLAGS_DISABLE_TOTP, True)
    account_objects.org.save()

    other = Organization.objects.create(name="other-mfa", slug="other-mfa")
    other.set_org_flag(settings.ORG_FLAGS_PASSKEY_REQUIRE_MFA, True)
    other.save()
    other.add_user(user)

    policy = effective_mfa_policy(user)
    assert policy["disable_totp"] is True
    assert policy["require_passkey_mfa"] is True
    assert policy["disable_password"] is False


# -------- user_has_satisfying_2fa --------


def test_user_has_satisfying_2fa_no_devices(db, account_objects):
    assert (
        user_has_satisfying_2fa(account_objects.user, {"disable_totp": False}) is False
    )


def test_user_has_satisfying_2fa_totp_only(db, account_objects):
    user = account_objects.user
    TOTPDevice.objects.create(user=user, name="phone", confirmed=True, key="0" * 40)

    assert user_has_satisfying_2fa(user, {"disable_totp": False}) is True
    # disable_totp policy must reject a TOTP-only user
    assert user_has_satisfying_2fa(user, {"disable_totp": True}) is False


def test_user_has_satisfying_2fa_static_backup(db, account_objects):
    user = account_objects.user
    StaticDevice.objects.create(user=user, name="backup", confirmed=True)

    # Backup codes count as MFA normally, but not under disable_totp.
    assert user_has_satisfying_2fa(user, {"disable_totp": False}) is True
    assert user_has_satisfying_2fa(user, {"disable_totp": True}) is False


# -------- EnforceMFA middleware --------


def _confirm_email(user):
    user.user_settings.email_confirmed = True
    user.user_settings.save()


def test_enforce_mfa_anonymous_no_redirect(db, client_anon):
    response = client_anon.get(reverse("account:controlpanel"))
    # Anonymous + login_required → 302 to LOGIN_URL, not to /two_factor/profile/
    assert response.status_code == 302
    assert "/two_factor/profile/" not in response["Location"]


def test_enforce_mfa_email_unconfirmed_skip(db, account_objects):
    # Flip a policy that would trap the user, then assert middleware lets
    # them through anyway because they haven't confirmed their email yet.
    account_objects.org.set_org_flag(settings.ORG_FLAGS_PASSKEY_REQUIRE_MFA, True)
    account_objects.org.save()
    assert account_objects.user.user_settings.email_confirmed is False

    response = account_objects.client.get(reverse("account:controlpanel"))
    assert response.status_code == 200


def test_enforce_mfa_require_passkey_no_devices_redirects(db, account_objects, mocker):
    _confirm_email(account_objects.user)
    account_objects.org.set_org_flag(settings.ORG_FLAGS_PASSKEY_REQUIRE_MFA, True)
    account_objects.org.save()

    mocker.patch("account.middleware.user_has_satisfying_2fa", return_value=False)

    response = account_objects.client.get(reverse("account:controlpanel"))

    assert response.status_code == 302
    assert response["Location"] == reverse("two_factor:profile")


def test_enforce_mfa_require_passkey_with_2fa_passes(db, account_objects, mocker):
    _confirm_email(account_objects.user)
    account_objects.org.set_org_flag(settings.ORG_FLAGS_PASSKEY_REQUIRE_MFA, True)
    account_objects.org.save()

    mocker.patch("account.middleware.user_has_satisfying_2fa", return_value=True)

    response = account_objects.client.get(reverse("account:controlpanel"))
    assert response.status_code == 200


def test_enforce_mfa_setup_required_session_marker_redirects(
    db, account_objects, mocker
):
    _confirm_email(account_objects.user)
    session = account_objects.client.session
    session["mfa_setup_required"] = True
    session.save()

    mocker.patch("account.middleware.user_has_satisfying_2fa", return_value=False)

    response = account_objects.client.get(reverse("account:controlpanel"))

    assert response.status_code == 302
    assert response["Location"] == reverse("two_factor:profile")


def test_enforce_mfa_setup_required_clears_when_satisfied(db, account_objects, mocker):
    _confirm_email(account_objects.user)
    session = account_objects.client.session
    session["mfa_setup_required"] = True
    session.save()

    mocker.patch("account.middleware.user_has_satisfying_2fa", return_value=True)

    response = account_objects.client.get(reverse("account:controlpanel"))

    assert response.status_code == 200
    # marker should have been cleared so subsequent navigation isn't gated
    assert "mfa_setup_required" not in account_objects.client.session


def test_enforce_mfa_excluded_prefixes():
    for path in (
        "/account/login/",
        "/account/two_factor/",
        "/security-keys/manage/",
        "/account/auth/login/",
        "/account/auth/logout/",
        "/jsi18n/",
        settings.STATIC_URL + "x.js",
    ):
        assert EnforceMFA.is_path_excluded(path), path

    assert not EnforceMFA.is_path_excluded("/account/")
    assert not EnforceMFA.is_path_excluded("/billing/")


# -------- ProfileView (MFA setup page) messaging --------
# EnforceMFA bounces an unsatisfied user to the MFA page without setting a
# message, so ProfileView derives the "why am I here" alert from current policy.


def test_profile_shows_policy_message_when_mfa_required(db, account_objects):
    _confirm_email(account_objects.user)
    account_objects.org.set_org_flag(settings.ORG_FLAGS_PASSKEY_REQUIRE_MFA, True)
    account_objects.org.save()

    response = account_objects.client.get(reverse("two_factor:profile"))

    assert response.status_code == 200
    assert b"requires multi-factor authentication" in response.content


def test_profile_no_policy_message_when_not_required(db, account_objects):
    _confirm_email(account_objects.user)

    response = account_objects.client.get(reverse("two_factor:profile"))

    assert response.status_code == 200
    assert b"requires multi-factor authentication" not in response.content


def test_profile_no_policy_message_when_satisfied(db, account_objects, mocker):
    # Enrolling a satisfying device clears the alert (condition goes false).
    _confirm_email(account_objects.user)
    account_objects.org.set_org_flag(settings.ORG_FLAGS_PASSKEY_REQUIRE_MFA, True)
    account_objects.org.save()
    mocker.patch("account.views.auth.user_has_satisfying_2fa", return_value=True)

    response = account_objects.client.get(reverse("two_factor:profile"))

    assert response.status_code == 200
    assert b"requires multi-factor authentication" not in response.content


def test_profile_login_message_takes_precedence(db, account_objects):
    # A specific message stashed by the login wizard wins and is shown one-shot.
    _confirm_email(account_objects.user)
    account_objects.org.set_org_flag(settings.ORG_FLAGS_PASSKEY_REQUIRE_MFA, True)
    account_objects.org.save()
    session = account_objects.client.session
    session["passkey_mfa_error"] = "custom login-flow message"
    session.save()

    response = account_objects.client.get(reverse("two_factor:profile"))

    assert response.status_code == 200
    assert b"custom login-flow message" in response.content
    assert b"requires multi-factor authentication" not in response.content
    assert "passkey_mfa_error" not in account_objects.client.session


def test_profile_shows_totp_disabled_message_on_rebounce(db, account_objects):
    # Pinned here by the mfa_setup_required marker (not require_passkey_mfa)
    # with the one-shot login message already gone: ProfileView must still
    # explain the disable_totp lock-in on re-bounce.
    _confirm_email(account_objects.user)
    account_objects.org.set_org_flag(settings.ORG_FLAGS_DISABLE_TOTP, True)
    account_objects.org.save()
    TOTPDevice.objects.create(user=account_objects.user, name="totp", confirmed=True)
    session = account_objects.client.session
    session["mfa_setup_required"] = True
    session.save()

    response = account_objects.client.get(reverse("two_factor:profile"))

    assert response.status_code == 200
    assert b"has disabled TOTP authentication" in response.content
    assert b"requires multi-factor authentication" not in response.content


# -------- REST: /api/account/org/{slug}/security/ --------


def _security_payload(response):
    """The fullctl REST renderer wraps responses as {data: [...], errors, profiling}."""
    body = response.json()
    assert body["errors"] in ({}, None), body
    return body["data"][0]


def test_org_security_get_default(db, account_objects):
    url = reverse("account_api:org-security", kwargs={"pk": account_objects.org.slug})
    response = account_objects.api_client.get(url)
    assert response.status_code == 200
    assert _security_payload(response) == {
        "disable_password": False,
        "disable_totp": False,
        "require_passkey_mfa": False,
    }


def test_org_security_put_full(db, account_objects):
    url = reverse("account_api:org-security", kwargs={"pk": account_objects.org.slug})
    response = account_objects.api_client.put(
        url,
        data={
            "disable_password": True,
            "disable_totp": True,
            "require_passkey_mfa": True,
        },
    )
    assert response.status_code == 200
    assert _security_payload(response) == {
        "disable_password": True,
        "disable_totp": True,
        "require_passkey_mfa": True,
    }
    account_objects.org.refresh_from_db()
    assert account_objects.org.disable_password is True
    assert account_objects.org.disable_totp is True
    assert account_objects.org.require_passkey_mfa is True


def test_org_security_put_partial_preserves_other_flags(db, account_objects):
    org = account_objects.org
    org.set_org_flag(settings.ORG_FLAGS_DISABLE_TOTP, True)
    org.save()

    url = reverse("account_api:org-security", kwargs={"pk": org.slug})
    response = account_objects.api_client.put(url, data={"require_passkey_mfa": True})
    assert response.status_code == 200
    org.refresh_from_db()
    # the unset key in the request body must not clobber existing flags
    assert org.disable_totp is True
    assert org.require_passkey_mfa is True


def test_org_security_unauthorized(db, account_objects):
    url = reverse("account_api:org-security", kwargs={"pk": account_objects.org.slug})
    # the read-only user lacks "manage" perms on the org
    response = account_objects.api_client_unperm.put(
        url, data={"disable_password": True}
    )
    assert response.status_code in (403, 404)


def test_org_security_anonymous(db, account_objects):
    url = reverse("account_api:org-security", kwargs={"pk": account_objects.org.slug})
    response = account_objects.api_client_anon.get(url)
    assert response.status_code == 403


# -------- password-path login --------

WIZARD_LOGIN_URL = "/account/login/"
WIZARD_PREFIX = "login_view"


def _add_totp(user):
    # name="default" so two_factor.utils.default_device() picks it up. Without
    # that, has_token_step() returns False and the wizard skips the token step.
    return TOTPDevice.objects.create(
        user=user, name="default", confirmed=True, key="0" * 40
    )


def _add_security_key(user, *, passkey_login, suffix=""):
    """Create a 2FA-only or passwordless-login key. The credential payload is
    a placeholder — these tests don't actually run a WebAuthn ceremony, they
    only assert that the wizard surfaces the security-key step."""
    return SecurityKey.objects.create(
        user=user,
        name="key" + suffix,
        credential_id="cred-" + str(user.id) + suffix,
        credential_public_key="pk-" + str(user.id) + suffix,
        type="public-key",
        passkey_login=passkey_login,
    )


def _submit_auth(client, username, password):
    return client.post(
        WIZARD_LOGIN_URL,
        {
            f"{WIZARD_PREFIX}-current_step": "auth",
            "auth-username": username,
            "auth-password": password,
        },
    )


def _set_org_flag(org, flag, value=True):
    org.set_org_flag(flag, value)
    org.save()


# --- Pwd-P1: no policy flags ---


def test_pwd_p1_no_devices_logs_in_directly(db, account_objects):
    """has_totp=F, passkey1=F, passkey2=F -> bare login (no 2FA enrolled)."""
    response = _submit_auth(Client(), account_objects.user.username, "test")
    assert response.status_code == 302
    assert "/account/login/" not in response["Location"]


def test_pwd_p1_totp_only_advances_to_token_step(db, account_objects):
    """has_totp=T, passkey1=F, passkey2=F -> wizard advances to token step."""
    _add_totp(account_objects.user)
    response = _submit_auth(Client(), account_objects.user.username, "test")
    assert response.status_code == 200
    assert response.context["wizard"]["steps"].current == "token"


def test_pwd_p1_security_key_advances_to_securitykey_step(db, account_objects):
    """has_totp=F, passkey2=T -> wizard advances to security-key step."""
    _add_security_key(account_objects.user, passkey_login=False)
    response = _submit_auth(Client(), account_objects.user.username, "test")
    assert response.status_code == 200
    assert response.context["wizard"]["steps"].current == "security-key"


def test_pwd_p1_totp_and_security_key_prefers_token_step(db, account_objects):
    """has_totp=T, passkey2=T -> token step is the default 2FA challenge."""
    _add_totp(account_objects.user)
    _add_security_key(account_objects.user, passkey_login=False)
    response = _submit_auth(Client(), account_objects.user.username, "test")
    assert response.status_code == 200
    assert response.context["wizard"]["steps"].current == "token"


# --- Pwd-P2: disable_totp=True ---


def test_pwd_p2_totp_only_redirects_to_setup(db, account_objects):
    """has_totp=T, disable_totp=T -> user has TOTP but org policy forbids it,
    so get_mfa_incomplete_redirect() pushes them to /two_factor/ to enrol
    a non-TOTP method. The library logs them in first so they can land on
    the setup page, then redirects."""
    _add_totp(account_objects.user)
    _set_org_flag(account_objects.org, settings.ORG_FLAGS_DISABLE_TOTP)
    response = _submit_auth(Client(), account_objects.user.username, "test")
    assert response.status_code == 302
    assert response["Location"] == reverse("two_factor:profile")


def test_pwd_p2_no_devices_logs_in_directly(db, account_objects):
    """has_totp=F, passkey=F, disable_totp=T -> nothing enrolled, no policy
    requires MFA. get_mfa_incomplete_redirect()'s else branch returns None
    and login proceeds without challenge. Not a security gap (no MFA to
    bypass) but worth pinning so a future tightening surfaces here."""
    _set_org_flag(account_objects.org, settings.ORG_FLAGS_DISABLE_TOTP)
    response = _submit_auth(Client(), account_objects.user.username, "test")
    assert response.status_code == 302
    assert "/two_factor/" not in response["Location"]
    assert "/account/login/" not in response["Location"]


def test_pwd_p2_security_key_advances_to_securitykey_step(db, account_objects):
    """has_totp=F, passkey2=T, disable_totp=T -> security-key step."""
    _add_security_key(account_objects.user, passkey_login=False)
    _set_org_flag(account_objects.org, settings.ORG_FLAGS_DISABLE_TOTP)
    response = _submit_auth(Client(), account_objects.user.username, "test")
    assert response.status_code == 200
    assert response.context["wizard"]["steps"].current == "security-key"


def test_pwd_p2_totp_and_security_key_skips_to_securitykey(db, account_objects):
    """has_totp=T, passkey2=T, disable_totp=T -> token suppressed, security-key shown."""
    _add_totp(account_objects.user)
    _add_security_key(account_objects.user, passkey_login=False)
    _set_org_flag(account_objects.org, settings.ORG_FLAGS_DISABLE_TOTP)
    response = _submit_auth(Client(), account_objects.user.username, "test")
    assert response.status_code == 200
    assert response.context["wizard"]["steps"].current == "security-key"


# --- disable_password policy ---


def test_password_blocked_when_org_disables_password_auth(db, account_objects):
    """disable_password=T → password login rejected, redirected back to login
    with a passkey_required_error stashed in the session."""
    _set_org_flag(account_objects.org, settings.ORG_FLAGS_PASSKEY_DISABLE_PASSWORD_AUTH)
    client = Client()
    response = _submit_auth(client, account_objects.user.username, "test")
    assert response.status_code == 302
    assert "/account/login/" in response["Location"]
    assert client.session.get("passkey_required_error")


# -------- Backup-tokens reauth gate --------

BACKUP_TOKENS_URL = "/account/two_factor/backup/tokens/"
BACKUP_TOKENS_CONFIRM_URL = "/account/two_factor/backup/tokens/confirm/"


def _add_static_backup(user, token="ABCD1234"):
    device, _ = StaticDevice.objects.get_or_create(
        user=user, name="backup", defaults={"confirmed": True}
    )
    device.confirmed = True
    device.save()
    StaticToken.objects.create(device=device, token=token)
    return device


# Patch target for the reauth-marker freshness check. Mocking this directly
# bypasses Django's session-storage round-trip in tests — the goal here is to
# exercise the view's dispatch + regen logic, not the session middleware.
_REAUTH_FRESH = "account.views.auth._backup_tokens_reauth_fresh"


# --- BackupTokensView dispatch gate ---


def test_backup_tokens_no_marker_redirects_to_confirm(db, account_objects, mocker):
    mocker.patch(_REAUTH_FRESH, return_value=False)
    response = account_objects.client.get(BACKUP_TOKENS_URL)
    assert response.status_code == 302
    assert response["Location"] == reverse("two_factor:backup_tokens_confirm")


def test_backup_tokens_fresh_marker_shows_page(db, account_objects, mocker):
    mocker.patch(_REAUTH_FRESH, return_value=True)
    response = account_objects.client.get(BACKUP_TOKENS_URL)
    assert response.status_code == 200


def test_backup_tokens_stale_marker_redirects_to_confirm(db, account_objects, mocker):
    """The freshness helper itself returns False for stale timestamps; this test
    pins that behavior at the dispatch layer (helper returns False -> redirect)."""
    mocker.patch(_REAUTH_FRESH, return_value=False)
    response = account_objects.client.get(BACKUP_TOKENS_URL)
    assert response.status_code == 302
    assert response["Location"] == reverse("two_factor:backup_tokens_confirm")


def test_backup_tokens_regen_with_fresh_marker_creates_tokens(
    db, account_objects, mocker
):
    mocker.patch(_REAUTH_FRESH, return_value=True)
    response = account_objects.client.post(BACKUP_TOKENS_URL, {"understand": "on"})
    assert response.status_code == 302
    device, _ = account_objects.user.staticdevice_set.get_or_create(name="backup")
    assert device.token_set.count() == 10


def test_backup_tokens_regen_without_understand_invalid(db, account_objects, mocker):
    mocker.patch(_REAUTH_FRESH, return_value=True)
    # Seed an existing token set so we can prove it wasn't wiped
    _add_static_backup(account_objects.user, token="ORIGINAL")
    response = account_objects.client.post(BACKUP_TOKENS_URL, {})
    assert response.status_code == 200
    assert response.context["form"].errors  # form invalid
    device = account_objects.user.staticdevice_set.get(name="backup")
    assert device.token_set.filter(token="ORIGINAL").exists()


def test_backup_tokens_regen_without_marker_redirects(db, account_objects, mocker):
    """POST without the marker is gated the same as GET — no codes rotated."""
    mocker.patch(_REAUTH_FRESH, return_value=False)
    _add_static_backup(account_objects.user, token="ORIGINAL")
    response = account_objects.client.post(BACKUP_TOKENS_URL, {"understand": "on"})
    assert response.status_code == 302
    assert response["Location"] == reverse("two_factor:backup_tokens_confirm")
    device = account_objects.user.staticdevice_set.get(name="backup")
    assert device.token_set.filter(token="ORIGINAL").exists()


# --- Reauth freshness helper (unit) ---


def test_reauth_fresh_returns_true_for_recent_timestamp():
    class _Req:
        session = {settings.BACKUP_TOKENS_REAUTH_SESSION_KEY: time.time()}

    assert _backup_tokens_reauth_fresh(_Req()) is True


def test_reauth_fresh_returns_false_for_stale_timestamp():
    class _Req:
        session = {
            settings.BACKUP_TOKENS_REAUTH_SESSION_KEY: time.time()
            - settings.BACKUP_TOKENS_REAUTH_TTL
            - 60
        }

    assert _backup_tokens_reauth_fresh(_Req()) is False


def test_reauth_fresh_returns_false_for_missing_marker():
    class _Req:
        session = {}

    assert _backup_tokens_reauth_fresh(_Req()) is False


# --- BackupTokensConfirmView ---


def test_backup_tokens_confirm_get_renders(db, account_objects):
    response = account_objects.client.get(BACKUP_TOKENS_CONFIRM_URL)
    assert response.status_code == 200


def test_backup_tokens_confirm_valid_token_sets_marker_and_redirects(
    db, account_objects
):
    _add_static_backup(account_objects.user, token="GOODCODE")
    response = account_objects.client.post(
        BACKUP_TOKENS_CONFIRM_URL,
        {"understand": "on", "otp_token": "GOODCODE"},
    )
    assert response.status_code == 302
    assert response["Location"] == reverse("two_factor:backup_tokens")
    ts = account_objects.client.session.get(settings.BACKUP_TOKENS_REAUTH_SESSION_KEY)
    assert isinstance(ts, (int, float))


def test_backup_tokens_confirm_invalid_token_blocks(db, account_objects):
    _add_static_backup(account_objects.user, token="GOODCODE")
    response = account_objects.client.post(
        BACKUP_TOKENS_CONFIRM_URL,
        {"understand": "on", "otp_token": "WRONGCODE"},
    )
    assert response.status_code == 200
    assert response.context["form"].errors
    assert (
        settings.BACKUP_TOKENS_REAUTH_SESSION_KEY not in account_objects.client.session
    )


def test_backup_tokens_confirm_no_proof_blocks(db, account_objects):
    """No otp_token and no credential — clean() must reject."""
    response = account_objects.client.post(
        BACKUP_TOKENS_CONFIRM_URL, {"understand": "on"}
    )
    assert response.status_code == 200
    assert response.context["form"].errors
    assert (
        settings.BACKUP_TOKENS_REAUTH_SESSION_KEY not in account_objects.client.session
    )


# --- DisableView clears the marker (defense in depth) ---


def test_disable_view_clears_backup_tokens_marker(db, account_objects):
    """After disabling 2FA, any leftover backup-tokens reauth marker must be
    cleared so the next visit to /backup/tokens/ forces fresh reauth. Real
    flow: user generated tokens (marker fresh) -> disabled TOTP -> next visit
    to backup-tokens should hit the confirm gate again."""
    _add_static_backup(account_objects.user, token="DISABLECODE")
    session = account_objects.client.session
    session[settings.BACKUP_TOKENS_REAUTH_SESSION_KEY] = time.time()
    session.save()

    response = account_objects.client.post(
        "/account/two_factor/disable/",
        {"understand": "on", "otp_token": "DISABLECODE"},
    )

    assert response.status_code == 302
    assert (
        settings.BACKUP_TOKENS_REAUTH_SESSION_KEY not in account_objects.client.session
    )
