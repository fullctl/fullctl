from datetime import timedelta

import pytest
import requests
import requests_mock
from django.db import IntegrityError, transaction
from django.utils import timezone

from fullctl.django.models.concrete.meta import Request as GenericRequest
from tests.django_tests.testapp.models import Data, Request, Response


@pytest.fixture
def db_data():
    return Data(
        source_name="test",
        type="info",
        data={"key": "value"},
        date="2022-01-01T00:00:00Z",
    )


@pytest.fixture
def db_data_old():
    return Data(
        source_name="test",
        type="info",
        data={"old_key": "old_value"},
        date="2021-01-01T00:00:00Z",
    )


@pytest.fixture
def db_request():
    return Request(
        source="test", type="info", url="http://testurl.com", http_status=200
    )


@pytest.fixture
def db_response(db_request):
    return Response(request=db_request, source="test", data={"key": "value"})


def test_data_model(db_data):
    assert db_data.source_name == "test"
    assert db_data.type == "info"
    assert db_data.data == {"key": "value"}
    assert (
        db_data.date == "2022-01-01T00:00:00Z"
    )  # Compare the date attribute to a string


def test_request_model(db_request):
    assert db_request.source == "test"
    assert db_request.type == "info"
    assert db_request.url == "http://testurl.com"
    assert db_request.http_status == 200


def test_response_model(db_response):
    assert db_response.source == "test"
    assert db_response.data == {"key": "value"}
    assert db_response.request.source == "test"


@pytest.mark.django_db
def test_request_send(db_request):
    with requests_mock.Mocker() as m:
        m.get("http://testurl.com", text='{"key": "value"}')
        request = Request.send("http://testurl.com")
        assert request.response.data == {"key": "value"}


@pytest.mark.django_db
def test_request_send_429_retry(db_request):
    with requests_mock.Mocker() as m:
        m.get(
            "http://testurl.com",
            [{"status_code": 429}, {"status_code": 200, "text": '{"key": "value"}'}],
        )
        request = Request.send("http://testurl.com")
        assert request.response.data == {"key": "value"}


@pytest.mark.django_db
def test_request_send_error(db_request):
    with requests_mock.Mocker() as m:
        m.get("http://testurl.com", exc=requests.exceptions.ConnectTimeout)
        with pytest.raises(requests.exceptions.ConnectTimeout):
            db_request.send("http://testurl.com")


@pytest.mark.django_db
def test_request_send_request(db_request):
    with requests_mock.Mocker() as m:
        m.get("http://testurl.com", text='{"key": "value"}')
        response = db_request.send_request("http://testurl.com")
        assert response.text == '{"key": "value"}'


@pytest.mark.django_db
def test_request_process(db_request):
    with requests_mock.Mocker() as m:
        m.get("http://testurl.com", text='{"key": "value"}')
        _resp = db_request.send_request("http://testurl.com")
        processed_request = db_request.process(
            "test_target", "http://testurl.com", _resp.status_code, lambda: _resp.json()
        )
        assert processed_request.http_status == 200
        assert processed_request.response.data == {"key": "value"}


@pytest.mark.django_db
def test_request_unique_cache_key_constraint():
    """
    A duplicate (source, url) row must raise IntegrityError. type=None on both
    proves the NULL hole is closed -- the old (source, type, url) key would not
    have collided, since SQL UNIQUE treats NULLs as distinct.
    """
    params = dict(
        target="test_target",
        url="http://testurl.com",
        source="test",
        type=None,
    )
    Request.objects.create(http_status=200, **params)

    with pytest.raises(IntegrityError):
        # atomic() so the failed INSERT doesn't poison the test transaction
        with transaction.atomic():
            Request.objects.create(http_status=200, **params)


@pytest.mark.django_db
def test_generic_request_unique_cache_key_constraint():
    """
    Same constraint on the generic request cache (concrete.meta.Request ->
    `request` table, used by arin-api). Guards its Meta inheritance + the
    django_fullctl migration, which the test app model can't exercise.
    """
    params = dict(
        identifier="203.0.113.0/24",
        url="http://example.test/generic",
        source="arin-api",
    )
    GenericRequest.objects.create(http_status=200, **params)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            GenericRequest.objects.create(http_status=200, **params)


@pytest.mark.django_db
def test_request_process_recovers_from_insert_race():
    """
    On losing the insert race, process() must reuse the winning row rather than
    propagate IntegrityError. Reproduced deterministically: an existing row has
    type="live" while process() computes type=None, so the initial lookup (which
    includes type) misses, the insert collides on (source, url), and it recovers.
    """
    winner = Request.objects.create(
        target="test_target",
        url="http://testurl.com",
        source="test",
        type="live",
        http_status=200,
        count=1,
    )

    result = Request.process("test_target", "http://testurl.com", 200, {"key": "value"})

    # recovered onto the existing row, bumped its count, no duplicate inserted
    assert result.pk == winner.pk
    winner.refresh_from_db()
    assert winner.count == 2
    assert Request.objects.filter(source="test", url="http://testurl.com").count() == 1


@pytest.mark.django_db
def test_request_process_refresh_does_not_trip_constraint():
    """
    Processing the same target twice must reuse the single row and bump its
    count, not insert a duplicate -- the normal refresh path must not trip the
    constraint (which would otherwise break every cache refresh).
    """
    Request.process("test_target", "http://testurl.com", 200, {"key": "value"})
    Request.process("test_target", "http://testurl.com", 200, {"key": "value"})

    rows = Request.objects.filter(url="http://testurl.com")
    assert rows.count() == 1
    assert rows.first().count == 2


@pytest.mark.django_db
def test_request_get_cache(db_request):
    cache = db_request.get_cache("test_target")
    assert cache is None  # Initially, there should be no cache


@pytest.mark.django_db
def test_response_write_meta_data(db_response, db_request):
    db_response.write_meta_data(db_request)
    data_entry = Data.objects.filter(source_name="test").first()

    for data in Data.objects.all():
        print(data.source_name, data.type, data.date, data.data)

    assert data_entry is not None
    assert data_entry.data == {"key": "value"}


def test_data_model_update(db_data):
    db_data.update({"new_key": "new_value"})
    assert db_data.data == {"new_key": "new_value"}


def test_request_model_prepare_request(db_request):
    single_target = "http://single-target.com"
    multiple_targets = ["http://target1.com", "http://target2.com"]
    assert db_request.prepare_request(single_target) == [single_target]
    assert db_request.prepare_request(multiple_targets) == multiple_targets


@pytest.mark.django_db
def test_request_model_send(db_request):
    with requests_mock.Mocker() as m:
        m.get("http://testurl.com", text='{"key": "value"}')
        request = Request.send("http://testurl.com")
        assert request.source == "test"
        assert request.url == "http://testurl.com"
        assert request.http_status == 200


@pytest.mark.django_db
def test_response_model_write_meta_data(db_response, db_request):
    db_response.write_meta_data(db_request)
    data_entry = Data.objects.filter(source_name="test").first()
    assert data_entry is not None
    assert data_entry.data == {"key": "value"}


@pytest.mark.django_db
def test_invalid_http_status_no_meta_update(db_request):
    """
    Test that an invalid http status does not cause an update of the meta data.
    """
    with requests_mock.Mocker() as m:
        # Simulate an invalid http status
        m.get("http://testurl.com", status_code=404, text='{"error": "not found"}')
        request = Request.send("http://testurl.com")

        # Check that the http status is indeed invalid
        assert request.http_status == 404

        # Check that the meta data is not updated
        data_entry = Data.objects.filter(source_name="test").first()
        assert data_entry is None


@pytest.mark.django_db
def test_request_429_cache_expiry(db_request):
    """
    Test that if a 429 response ends up in the cache, it is considered expired after 5 minutes.
    """
    with requests_mock.Mocker() as m:
        # Simulate a 429 status
        m.get("http://testurl.com", status_code=429)
        request = Request.send("http://testurl.com")

        # Check that the http status is 429
        assert request.http_status == 429

        # Manually set the updated time of the request to be more than 5 minutes ago
        request._meta.get_field("updated").auto_now = False
        request.updated = timezone.now() - timedelta(minutes=6)
        request.save()
        request._meta.get_field("updated").auto_now = True

        # Check that the cached request is considered expired
        cached_request = Request.get_cache("http://testurl.com")
        assert cached_request is None


@pytest.mark.django_db
def test_request_5xx_cache_expiry(db_request):
    """
    Test that if a 5xx response ends up in the cache, it is considered expired after 1 minute (SERVER_ERROR_CACHE_EXPIRY).
    """
    with requests_mock.Mocker() as m:
        m.get("http://testurl.com", status_code=500)
        request = Request.send("http://testurl.com")

        assert request.http_status == 500

        request._meta.get_field("updated").auto_now = False
        request.updated = timezone.now() - timedelta(minutes=2)
        request.save()
        request._meta.get_field("updated").auto_now = True

        cached_request = Request.get_cache("http://testurl.com")
        assert cached_request is None


@pytest.mark.django_db
def test_request_5xx_cache_not_expired_within_timeout(db_request):
    """
    Test that a 5xx response in the cache is still valid within the SERVER_ERROR_CACHE_EXPIRY timeout.
    """
    with requests_mock.Mocker() as m:
        m.get("http://testurl.com", status_code=502)
        request = Request.send("http://testurl.com")

        assert request.http_status == 502

        request._meta.get_field("updated").auto_now = False
        request.updated = timezone.now() - timedelta(seconds=30)
        request.save()
        request._meta.get_field("updated").auto_now = True

        cached_request = Request.get_cache("http://testurl.com")
        assert cached_request is not None
        assert cached_request.http_status == 502


@pytest.mark.django_db
def test_old_entry_not_overwritten(db_request, db_response):
    """
    Test that if an entry is old enough, it is not overwritten but a new entry is added instead.
    """
    with requests_mock.Mocker() as m:
        # Simulate a 200 status
        m.get("http://testurl.com", status_code=200, text='{"key": "old_value"}')
        request = Request.send("http://testurl.com")

        # Check that the http status is 200
        assert request.http_status == 200

        # Manually set the date of the data entry to be more than 12 hours ago
        # Using .update() to bypass the auto_now behavior of the updated field
        Data.objects.filter(source_name="test").update(
            date=timezone.now() - timedelta(hours=13)
        )

        # Update the data
        m.get("http://testurl.com", status_code=200, text='{"key": "new_value"}')
        request = Request.send("http://testurl.com")

        # Check that a new entry is created instead of overwriting the old one
        data_entries = Data.objects.filter(source_name="test")
        assert len(data_entries) == 2
        assert data_entries[0].data == {"key": "old_value"}
        assert data_entries[1].data == {"key": "new_value"}
