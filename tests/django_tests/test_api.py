import json
from django.urls import reverse
from django.contrib.auth import get_user_model

import fullctl.django.models as models

def test_list_orgs(db, pdb_data, account_objects):
    ix = account_objects.ix
    client = account_objects.api_client
    org = account_objects.org

    response = client.get(reverse("fullctl_account_api:org-list"))

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data) == len(account_objects.orgs)
    assert set([d["name"] for d in data]) == set([
        org.display_name for org in account_objects.orgs
    ])