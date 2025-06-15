import json

from django.contrib.auth import authenticate
from django.urls import reverse

import account.models as models
from tests.helpers import assert_expected, strip_api_fields


def test_api_key_auth_urlparam(db, account_objects, data_account_api_user_list):
    """
    tests api key authentication using the `key` url paramater
    """

    response = account_objects.api_client_anon.get(reverse("account_api:user-list"))

    print(response.headers)

    assert response.status_code == 403

    response = account_objects.api_client_anon.get(
        reverse("account_api:user-list") + f"?key={account_objects.api_key.key}"
    )

    assert response.status_code == 200
    assert strip_api_fields(response.json()) == data_account_api_user_list.expected


def test_api_key_auth_header(db, account_objects, data_account_api_user_list):
    """
    tests api key authentication using the `Authorization` HTTP header
    """

    response = account_objects.api_client_anon.get(reverse("account_api:user-list"))

    assert response.status_code == 403

    response = account_objects.api_client_anon.get(
        reverse("account_api:user-list"),
        HTTP_AUTHORIZATION=f"Bearer {account_objects.api_key.key}",
    )

    assert response.status_code == 200
    assert strip_api_fields(response.json()) == data_account_api_user_list.expected


def test_user_list(db, account_objects, data_account_api_user_list):
    response = account_objects.api_client.get(reverse("account_api:user-list"))

    assert response.status_code == 200
    assert strip_api_fields(response.json()) == data_account_api_user_list.expected

    # test unauthenticated user

    response = account_objects.api_client_anon.get(reverse("account_api:user-list"))

    assert response.status_code == 403


def test_user_put(db, account_objects, data_account_api_user_put):
    response = account_objects.api_client.put(
        reverse("account_api:user-list"),
        data=json.loads(data_account_api_user_put.input),
    )

    assert response.status_code == int(data_account_api_user_put.status)
    assert strip_api_fields(response.json()) == data_account_api_user_put.expected

    # test unauthenticated user

    response = account_objects.api_client_anon.put(
        reverse("account_api:user-list"),
        data=json.loads(data_account_api_user_put.input),
    )

    assert response.status_code == 403


def test_user_set_password(db, account_objects, data_account_api_user_setpassword):
    response = account_objects.api_client.put(
        reverse("account_api:user-set-password"),
        data=json.loads(data_account_api_user_setpassword.input),
    )

    assert response.status_code == int(data_account_api_user_setpassword.status)
    assert (
        strip_api_fields(response.json()) == data_account_api_user_setpassword.expected
    )

    # test unauthenticated user

    response = account_objects.api_client_anon.put(
        reverse("account_api:user-set-password"),
        data=json.loads(data_account_api_user_setpassword.input),
    )

    assert response.status_code == 403


def test_user_resend_confirmation_mail(db, account_objects):
    response = account_objects.api_client.post(
        reverse("account_api:user-resend-confirmation-mail")
    )

    assert response.status_code == 200

    account_objects.user.email_confirmation.complete()

    # test when email has already been confirmed

    response = account_objects.api_client.post(
        reverse("account_api:user-resend-confirmation-mail")
    )

    assert response.status_code == 400

    # test unauthenticated user

    response = account_objects.api_client_anon.post(
        reverse("account_api:user-resend-confirmation-mail")
    )

    assert response.status_code == 403


def test_org_list(db, account_objects, data_account_api_org_list):
    response = account_objects.api_client.get(reverse("account_api:org-list"))

    assert response.status_code == int(data_account_api_org_list.status)
    assert strip_api_fields(response.json()) == strip_api_fields(
        data_account_api_org_list.expected
    )

    # test unauthenticated user

    response = account_objects.api_client_anon.get(reverse("account_api:org-list"))

    assert response.status_code == 403


def test_org_details(db, account_objects, data_account_api_org_details):
    response = account_objects.api_client.get(
        reverse("account_api:org-detail", args=(account_objects.org.slug,))
    )

    assert response.status_code == int(data_account_api_org_details.status)
    assert strip_api_fields(response.json()) == strip_api_fields(
        data_account_api_org_details.expected
    )

    # test unauthenticated user

    response = account_objects.api_client_anon.get(
        reverse("account_api:org-detail", args=(account_objects.org.slug,))
    )

    assert response.status_code == 403


def test_org_create(db, account_objects, data_account_api_org_create):
    response = account_objects.api_client.post(
        reverse("account_api:org-list"),
        data=json.loads(data_account_api_org_create.input),
    )

    assert response.status_code == int(data_account_api_org_create.status)
    assert strip_api_fields(response.json()) == strip_api_fields(
        data_account_api_org_create.expected
    )

    # test unauthenticated user

    response = account_objects.api_client_anon.post(
        reverse("account_api:org-list"),
        data=json.loads(data_account_api_org_create.input),
    )

    assert response.status_code == 403


def test_org_update(db, account_objects, data_account_api_org_update):
    if data_account_api_org_update.name == "test_error_permissions":
        slug = account_objects.other_org.slug
    else:
        slug = account_objects.org.slug

    response = account_objects.api_client.put(
        reverse("account_api:org-detail", args=(slug,)),
        data=json.loads(data_account_api_org_update.input),
    )

    assert response.status_code == int(data_account_api_org_update.status)
    if data_account_api_org_update.name != "test_error_permissions":
        assert strip_api_fields(response.json()) == strip_api_fields(
            data_account_api_org_update.expected
        )

    # test unauthenticated user

    response = account_objects.api_client_anon.post(
        reverse("account_api:org-list"),
        data=json.loads(data_account_api_org_update.input),
    )

    assert response.status_code == 403


def test_org_users(db, account_objects, data_account_api_org_users):
    slug = account_objects.org.slug

    response = account_objects.api_client.get(
        reverse("account_api:org-users", args=(slug,))
    )

    assert response.status_code == int(data_account_api_org_users.status)

    assert strip_api_fields(response.json()) == strip_api_fields(
        data_account_api_org_users.expected
    )

    # test user not part of org

    response = account_objects.api_client_anon.get(
        reverse("account_api:org-users", args=(account_objects.other_org.slug,))
    )

    assert response.status_code == 403

    # test unauthenticated user

    response = account_objects.api_client_anon.get(
        reverse("account_api:org-users", args=(slug,))
    )

    assert response.status_code == 403


def test_org_userdel(db, account_objects, data_account_api_org_userdel):
    slug = account_objects.org.slug

    data = {}

    if data_account_api_org_userdel.name == "test0":
        data.update(
            id=account_objects.user_unpermissioned.org_user_set.filter(
                org=account_objects.org
            )
            .first()
            .id
        )
    else:
        data.update(
            id=account_objects.user.org_user_set.filter(org=account_objects.org)
            .first()
            .id
        )

    response = account_objects.api_client.delete(
        reverse("account_api:org-user", args=(slug,)),
        data=data,
    )

    assert response.status_code == int(data_account_api_org_userdel.status)
    assert strip_api_fields(response.json()) == strip_api_fields(
        data_account_api_org_userdel.expected
    )

    if data_account_api_org_userdel.name == "test0":
        assert account_objects.org.org_user_set.count() == 1

    # test user not part of org

    response = account_objects.api_client_anon.delete(
        reverse("account_api:org-user", args=(account_objects.other_org.slug,)),
        data=json.loads(data_account_api_org_userdel.input),
    )

    assert response.status_code == 403

    # test unauthenticated user

    response = account_objects.api_client_anon.delete(
        reverse("account_api:org-user", args=(slug,)),
        data=json.loads(data_account_api_org_userdel.input),
    )

    assert response.status_code == 403


def test_org_set_permissions(db, account_objects, data_account_api_org_setperm):
    input = json.loads(data_account_api_org_setperm.input)
    expected = data_account_api_org_setperm.expected
    slug = input.get("slug", account_objects.org.slug)

    input["data"].update(
        id=account_objects.user_unpermissioned.org_user_set.filter(
            org=account_objects.org
        )
        .first()
        .id
    )

    response = getattr(account_objects, input["client"]).put(
        reverse("account_api:org-set-permissions", args=(slug,)), data=input["data"]
    )

    assert_expected(response, expected)


def test_org_invite(db, account_objects, data_account_api_org_invite):
    input = json.loads(data_account_api_org_invite.input)
    expected = data_account_api_org_invite.expected
    slug = input.get("slug", account_objects.org.slug)

    response = getattr(account_objects, input["client"]).post(
        reverse("account_api:org-invite", args=(slug,)), data=input["data"]
    )

    assert_expected(response, strip_api_fields(expected))


def test_org_admininvite(db, account_objects, data_account_api_org_invite):
    input = json.loads(data_account_api_org_invite.input)
    expected = data_account_api_org_invite.expected
    slug = input.get("slug", account_objects.org.slug)

    response = getattr(account_objects, input["client"]).post(
        reverse("account_api:org-invite", args=(slug,)), data=input["data"]
    )

    assert_expected(response, strip_api_fields(expected))


def test_password_reset_start(
    db, account_objects, data_account_api_password_reset_start
):
    input = json.loads(data_account_api_password_reset_start.input)
    expected = data_account_api_password_reset_start.expected

    response = getattr(account_objects, input["client"]).post(
        reverse("account_api:password_reset-start"), data=input["data"]
    )

    assert_expected(response, expected)


def test_password_reset_complete(
    db, account_objects, data_account_api_password_reset_complete
):
    password_reset = models.PasswordReset.start(account_objects.user)

    input = json.loads(data_account_api_password_reset_complete.input)
    expected = data_account_api_password_reset_complete.expected
    data = input["data"]
    if data.get("secret") == "$":
        data["secret"] = password_reset.secret

    response = getattr(account_objects, input["client"]).post(
        reverse("account_api:password_reset-complete"), data=data
    )

    assert_expected(response, expected)

    if expected["status"] == 200:
        assert authenticate(
            username=account_objects.user.username, password=data["password_new"]
        )
