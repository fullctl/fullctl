import json

from django.contrib.auth import get_user_model
from django.urls import reverse

import fullctl.django.models as models


def test_list_orgs(db, dj_account_objects):
    client = dj_account_objects.api_client
    org = dj_account_objects.org

    response = client.get(reverse("fullctl_account_api:org-list"))

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == len(dj_account_objects.orgs)
    assert set([d["name"] for d in data]) == set([
        org.display_name for org in dj_account_objects.orgs
    ])