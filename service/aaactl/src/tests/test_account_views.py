from django.urls import reverse

import account.models as models
from account.views.auth import valid_frontend_redirect
from common.util import format_logo_url


def test_login(db, client_anon):
    response = client_anon.get(reverse("account:auth-login"))
    assert response.status_code == 200
    assert "Register New Account" in response.content.decode()


def test_login_no_signup_link(db, client_anon, settings):
    settings.ENABLE_ACCOUNT_REGISTRATION = 0
    response = client_anon.get(reverse("account:auth-login"))
    assert response.status_code == 200
    assert "Register New Account" not in response.content.decode()


def test_login_signup_link_through_invitation(
    db, account_objects, client_anon, settings
):
    settings.ENABLE_ACCOUNT_REGISTRATION = 0
    invite = models.Invitation.objects.create(
        org=account_objects.org, created_by=account_objects.user, email="test@localhost"
    )

    response = client_anon.get(
        reverse("account:auth-login") + f"?invite={invite.secret}"
    )

    assert response.status_code == 200
    assert "Register New Account" in response.content.decode()
    assert "You have been invited to join the organization" in response.content.decode()


def test_register_disabled(db, client_anon, settings):
    settings.ENABLE_ACCOUNT_REGISTRATION = 0
    response = client_anon.get(reverse("account:auth-register"))
    assert response.status_code == 404


def test_register_through_invitation(db, account_objects, client_anon, settings):
    settings.ENABLE_ACCOUNT_REGISTRATION = 0
    invite = models.Invitation.objects.create(
        org=account_objects.org, created_by=account_objects.user, email="test@localhost"
    )

    response = client_anon.get(
        reverse("account:auth-register") + f"?invite={invite.secret}"
    )

    assert response.status_code == 200
    assert "You have been invited to join the organization" in response.content.decode()


def test_org_branding_slug_filtering(db, client_anon, account_objects, settings):
    settings.BRANDING_ORG = account_objects.org.slug
    response = client_anon.get(reverse("account:auth-login"))

    assert response.context["org_branding"]["name"] == account_objects.org.name


def test_org_branding_http_host_filtering(db, client_anon, account_objects):
    # http_host is set as testserver and settings.BRANDING_ORG is None
    account_objects.org_branding.http_host = "testserver"
    account_objects.org_branding.save()

    response = client_anon.get(reverse("account:auth-login"))

    assert response.context["org_branding"]["name"] == account_objects.org.name


def test_valid_frontend_redirect(db, settings, account_objects):
    settings.FRONTEND_ORIGINS = ["http://localhost:8080"]
    url = valid_frontend_redirect(
        "http://localhost:8080", reverse("account:controlpanel"), account_objects.user
    )
    assert url[:28] == "http://localhost:8080/login/"

    url = valid_frontend_redirect(
        "http://localhost:8081", reverse("account:controlpanel"), account_objects.user
    )
    assert url == reverse("account:controlpanel")


def test_login_frontend(db, account_objects, client_anon, settings):
    response = client_anon.get(reverse("account:auth-login-frontend"))
    assert response.status_code == 200

    settings.FRONTEND_ORIGINS = ["http://localhost:8080"]
    payload = {
        "username_or_email": account_objects.user.username,
        "password": "test",
        "next": "http://localhost:8080",
    }
    response = client_anon.post(
        reverse("account:auth-login-frontend"),
        data=payload,
    )
    assert response.status_code == 302
    assert response.url[:28] == "http://localhost:8080/login/"

    payload = {"next": "http://localhost:8080"}
    response = account_objects.client.get(
        reverse("account:auth-login-frontend"), payload
    )
    assert response.status_code == 302
    assert response.url[:28] == "http://localhost:8080/login/"


def test_logout(db, account_objects):
    response = account_objects.client.get(reverse("account:auth-logout"), follow=True)
    assert response.status_code == 200


def test_confirm_email(db, account_objects):
    email_confirmation = models.EmailConfirmation.start(account_objects.user)

    response = account_objects.client.get(
        reverse("account:auth-confirm-email", args=(email_confirmation.secret,)),
        follow=True,
    )

    assert response.status_code == 200

    assert (
        models.EmailConfirmation.objects.filter(user=account_objects.user).exists()
        is False
    )

    account_objects.user.user_settings.refresh_from_db()

    assert account_objects.user.user_settings.email_confirmed


def test_reset_password(db, account_objects, client_anon):
    response = client_anon.get(reverse("account:auth-reset-password-start"))

    assert response.status_code == 200

    password_reset = models.PasswordReset.start(account_objects.user)

    response = client_anon.get(
        reverse("account:auth-reset-password", args=(password_reset.secret,))
    )

    assert response.status_code == 200


def test_accept_invite(db, account_objects, account_objects_b):
    invite = models.Invitation.objects.create(
        org=account_objects.org, created_by=account_objects.user, email="test@localhost"
    )

    response = account_objects_b.client.get(
        reverse("account:accept-invite", args=(invite.secret,)), follow=True
    )

    assert response.status_code == 200

    account_objects_b.user.refresh_from_db()
    assert account_objects_b.user.org_user_set.filter(org=account_objects.org).exists()


def test_index(db, account_objects, client_anon):
    response = account_objects.client.get(reverse("account:controlpanel"))
    assert response.status_code == 200

    response = client_anon.get(reverse("account:controlpanel"))
    assert response.status_code == 302


def test_index_with_branding_org_var_set(db, account_objects, settings):
    settings.BRANDING_ORG = account_objects.org.slug
    response = account_objects.client.get(reverse("account:controlpanel"))

    assert response.status_code == 200
    assert response.context["org_branding"]["name"] == account_objects.org.name


def test_org_branding_favicon_url(db, client_anon, account_objects, settings):
    settings.BRANDING_ORG = account_objects.org.slug
    favicon_url = "https://{version}{static_path}"
    account_objects.org_branding.favicon_url = favicon_url
    account_objects.org_branding.save()

    response = client_anon.get(reverse("account:auth-login"))

    assert response.context["org_branding"]["favicon_url"] == format_logo_url(
        favicon_url
    )
