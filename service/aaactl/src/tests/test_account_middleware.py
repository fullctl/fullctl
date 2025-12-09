from django.urls import reverse


def test_select_org_default(db, account_objects, client_anon):
    client = account_objects.client
    response = client.get(reverse("account:controlpanel"))
    request = response.wsgi_request

    assert request.selected_org == account_objects.org

    response = client_anon.get(reverse("account:auth-login"))
    request = response.wsgi_request

    assert request.selected_org is None


def test_select_org_slug(db, account_objects, client_anon):
    client = account_objects.client
    org = account_objects.org
    other = account_objects.other_org

    response = client.get(reverse("account:controlpanel") + f"?org={org.slug}")
    request = response.wsgi_request

    assert request.selected_org == org

    response = client_anon.get(reverse("account:controlpanel") + f"?org={org.slug}")
    request = response.wsgi_request

    assert request.selected_org is None

    response = client.get(reverse("account:controlpanel") + f"?org={other.slug}")
    request = response.wsgi_request

    assert request.selected_org == org
