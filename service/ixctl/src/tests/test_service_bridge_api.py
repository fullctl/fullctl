import django_ixctl.models as models
from django.urls import reverse


def test_api_select_traffic_alert_config(db, account_objects):
    client = account_objects.api_client
    ix = account_objects.ix

    models.TrafficAlertConfig(
        ix=ix,
        traffic_level=90,
        time_period=5,
        operator_emails=True,
        member_emails=True,
        operator_emails_max_frequency=7,
        member_emails_max_frequency=7,
    ).save()

    api_url = reverse(
        "service_bridge_api:service-bridge-data-traffic_alert_config-list"
    )
    response = client.get(f"{api_url}?ix={ix.id}")

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["ix"] == ix.id


def test_api_select_email_template_ix(db, account_objects):
    client = account_objects.api_client
    ix = account_objects.ix
    member = ix.member_set.first()

    traffic_alert_config = models.TrafficAlertConfig(
        ix=ix,
        traffic_level=90,
        time_period=5,
        operator_emails=True,
        member_emails=True,
        operator_emails_max_frequency=7,
        member_emails_max_frequency=7,
    )
    traffic_alert_config.save()

    template_type = "traffic_alert_ix"
    models.EmailTemplate(
        ix=ix,
        name="Traffic Alert Net",
        body="Test email body for {{ ix.name }}",
        type=template_type,
    ).save()

    api_url = reverse(
        "service_bridge_api:service-bridge-data-traffic_alert_email-get-traffic-alert-email",
        args=(ix.id, template_type, member.id),
    )
    response = client.get(api_url)

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert data["data"][0]["subject"] == f"High port/LAG utilization notice: {ix.name}"
    assert data["data"][0]["message"] == f"Test email body for {ix.name}"


def test_api_select_email_template_net(db, account_objects):
    client = account_objects.api_client
    ix = account_objects.ix
    member = ix.member_set.first()

    traffic_alert_config = models.TrafficAlertConfig(
        ix=ix,
        traffic_level=90,
        time_period=5,
        operator_emails=True,
        member_emails=True,
        operator_emails_max_frequency=7,
        member_emails_max_frequency=7,
    )
    traffic_alert_config.save()

    template_type = "traffic_alert_net"
    models.EmailTemplate(
        ix=ix,
        name="Traffic Alert Net",
        body="Test email body for {{ ix.name }}",
        type=template_type,
    ).save()

    api_url = reverse(
        "service_bridge_api:service-bridge-data-traffic_alert_email-get-traffic-alert-email",
        args=(ix.id, template_type, member.id),
    )
    response = client.get(api_url)

    assert response.status_code == 200
    data = response.json()
    assert len(data["data"]) == 1
    assert (
        data["data"][0]["subject"]
        == f"High port/LAG utilization notice: {member.name} {member.asn}"
    )
    assert data["data"][0]["message"] == f"Test email body for {ix.name}"
