from django.urls import reverse


def test_permissions(db, account_objects, data_account_ctxp_perms):
    response = account_objects.client.get(reverse("account:controlpanel"))

    permissions = response.context["permissions"]

    assert permissions == data_account_ctxp_perms.expected
