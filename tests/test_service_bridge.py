import pytest

from fullctl.service_bridge.aaactl import PointOfContact
from fullctl.service_bridge.client import url_join


@pytest.mark.parametrize(
    "a,b,c,expected",
    [
        ("http://example.com", "foo", "bar", "http://example.com/foo/bar/"),
        ("http://example.com", "foo/", "/bar", "http://example.com/foo/bar/"),
        (
            "http://example.com",
            "foo/",
            "/bar/test/extra",
            "http://example.com/foo/bar/test/extra/",
        ),
        (
            "http://example.com",
            "foo/",
            "/bar/test//extra",
            "http://example.com/foo/bar/test/extra/",
        ),
        ("http://example.com/", "/foo/", "/bar/", "http://example.com/foo/bar/"),
        ("http://example.com/", "/foo//", "//bar/", "http://example.com/foo/bar/"),
        ("http://test/", "/foo//", "//bar/", "http://test/foo/bar/"),
        ("http://example.com/", "/foo/", "bar//", "http://example.com/foo/bar/"),
        (None, "/foo/", "bar//", "/foo/bar/"),
    ],
)
def test_urljoin(a, b, c, expected):
    """
    Tests that calling urljoin with  a,b and c will match the expected result
    """
    assert url_join(a, b, c) == expected


def test_aaactl_poc_merge_configs():
    configs = [
        {"service": "ixctl", "recipients": ["test@test.com", "email@email.com"]},
        {"service": "peerctl", "recipients": ["another@test.com", "email@email.com"]},
    ]
    update_configs = [
        {"service": "ixctl", "recipients": ["new@test.com", "ixtctl@email.com"]},
        {"service": "peerctl", "recipients": ["another@test.com", "third@email.com"]},
    ]
    result = PointOfContact.merge_configs(configs + update_configs)
    expected = [
        {
            "service": "ixctl",
            "recipients": [
                "test@test.com",
                "email@email.com",
                "new@test.com",
                "ixtctl@email.com",
            ],
        },
        {
            "service": "peerctl",
            "recipients": ["another@test.com", "email@email.com", "third@email.com"],
        },
    ]
    assert len(result) == 2

    for config in result:
        if config["service"] == "ixctl":
            assert len(config["recipients"]) == len(expected[0]["recipients"])
            assert set(config["recipients"]) == set(expected[0]["recipients"])
        if config["service"] == "peerctl":
            assert len(config["recipients"]) == len(expected[1]["recipients"])
            assert set(config["recipients"]) == set(expected[1]["recipients"])
