import time
from unittest.mock import MagicMock, patch

import pytest
from django_auditctl.limit import (
    TIME_WINDOWS,
    clean_old_timestamps,
    get_rate_limit,
    is_limited,
    parse_rate_limit,
    set_limited,
)


@pytest.mark.parametrize(
    "rate_str,expected",
    [
        ("1/second", (1, 1)),
        ("5/minute", (5, 60)),
        ("10/hour", (10, 3600)),
        ("100/second", (100, 1)),
        # Should raise ValueError
        ("invalid", None),
    ],
)
def test_parse_rate_limit(rate_str, expected):
    """Test parsing different rate limit strings."""
    if expected is None:
        with pytest.raises(ValueError):
            parse_rate_limit(rate_str)
    else:
        result = parse_rate_limit(rate_str)
        assert result == expected


@pytest.mark.parametrize(
    "object_id,expected",
    [
        # Matches first pattern - actual value from tests
        ("v0.1/demo/bgp/stat/192.0.2.1/64496/", (1, 1)),
        # Matches first pattern - actual value from tests
        ("v0.1/demo/bgp/stat/", (1, 1)),
        # No matching pattern
        ("v0.1/invalid/path", None),
    ],
)
def test_get_rate_limit(object_id, expected):
    """Test getting rate limits for different object IDs."""
    result = get_rate_limit(object_id)
    assert result == expected


@pytest.mark.parametrize(
    "timestamps,window_seconds,current_time,expected_count",
    [
        # All timestamps are within window
        ([100, 101, 102], 10, 105, 3),
        # All timestamps are within window (95 >= 105-10)
        ([95, 96, 105], 10, 105, 3),
        # No timestamps are within window
        ([90, 91, 92], 10, 105, 0),
        # Empty list
        ([], 10, 105, 0),
    ],
)
def test_clean_old_timestamps(timestamps, window_seconds, current_time, expected_count):
    """Test cleaning old timestamps that are outside the time window."""
    with patch("time.time", return_value=current_time):
        result = clean_old_timestamps("test_id", window_seconds, timestamps)
        assert len(result) == expected_count


@pytest.mark.parametrize(
    "object_id,rate_limit_result,cache_result,expected",
    [
        # No rate limit applies
        ("no_match", None, None, False),
        # Rate limit applies, but not limited
        ("v0.1/demo/bgp/stat/", (2, 60), [time.time() - 10], False),
        # Rate limit applies and is limited
        ("v0.1/demo/bgp/stat/", (2, 60), [time.time() - 10, time.time() - 5], True),
    ],
)
def test_is_limited(object_id, rate_limit_result, cache_result, expected):
    """Test checking if an object ID is rate-limited."""
    with patch("django_auditctl.limit.get_rate_limit", return_value=rate_limit_result):
        with patch(
            "django_auditctl.limit.ratelimit_cache.get", return_value=cache_result
        ):
            with patch("django_auditctl.limit.ratelimit_cache.set") as mock_cache_set:
                result = is_limited(object_id)
                assert result == expected


@pytest.mark.parametrize(
    "object_id,rate_limit_result,cache_result,expected_return,expected_timestamps",
    [
        # No rate limit applies
        ("no_match", None, None, False, None),
        # Rate limit applies, set timestamp
        ("v0.1/demo/bgp/stat/", (2, 60), [100], True, True),
    ],
)
def test_set_limited(
    object_id, rate_limit_result, cache_result, expected_return, expected_timestamps
):
    """Test recording an event for rate limiting purposes."""
    current_time = time.time()

    with patch("django_auditctl.limit.get_rate_limit", return_value=rate_limit_result):
        with patch(
            "django_auditctl.limit.ratelimit_cache.get", return_value=cache_result
        ):
            with patch("django_auditctl.limit.ratelimit_cache.set") as mock_cache_set:
                with patch("time.time", return_value=current_time):
                    result = set_limited(object_id)
                    assert result == expected_return

                    if expected_timestamps:
                        # Check cache was updated with our new timestamp
                        mock_cache_set.assert_called_once()
                        # Get the arguments passed to set
                        call_args = mock_cache_set.call_args
                        args, kwargs = call_args
                        # Verify there are at least some arguments
                        assert len(args) >= 2
                        # Extract key and value from the proper positions
                        cache_key, timestamps = args[0], args[1]
                        # Verify the timestamps list contains our current time
                        assert current_time in timestamps


@pytest.mark.parametrize(
    "object_id,initial_timestamps,limit,should_be_limited_first,should_be_limited_after_more",
    [
        # Test with a limit of 2/minute, no initial timestamps
        ("v0.1/demo/bgp/stat/test1", [], (2, 60), False, True),
        # Test with a limit of 3/hour, already has 2 timestamps
        (
            "v0.1/demo/bgp/stat/test2",
            [time.time() - 100, time.time() - 50],
            (3, 3600),
            False,
            True,
        ),
    ],
)
def test_rate_limiting_workflow(
    object_id,
    initial_timestamps,
    limit,
    should_be_limited_first,
    should_be_limited_after_more,
):
    """Integration test for a complete rate limiting workflow."""
    mock_cache = {}

    def mock_cache_get(key, default=None):
        return mock_cache.get(key, default)

    def mock_cache_set(key, value, timeout=None):
        mock_cache[key] = value

    # Set up initial state
    cache_key = f"ratelimit:{object_id}"
    if initial_timestamps:
        mock_cache[cache_key] = initial_timestamps

    with patch("django_auditctl.limit.get_rate_limit", return_value=limit):
        with patch(
            "django_auditctl.limit.ratelimit_cache.get", side_effect=mock_cache_get
        ):
            with patch(
                "django_auditctl.limit.ratelimit_cache.set", side_effect=mock_cache_set
            ):
                # First check if limited
                assert is_limited(object_id) == should_be_limited_first

                # Record first event
                set_limited(object_id)
                # Record second event
                set_limited(object_id)
                # Record third event
                set_limited(object_id)

                # Now should be limited based on our parameterization
                assert is_limited(object_id) == should_be_limited_after_more


def test_rate_limiting_different_object_ids():
    """Test that rate limiting for different object IDs don't interfere with each other."""
    mock_cache = {}

    def mock_cache_get(key, default=None):
        return mock_cache.get(key, default)

    def mock_cache_set(key, value, timeout=None):
        mock_cache[key] = value

    # Define two different object IDs
    object_id_1 = "v0.1/demo/bgp/stat/test1"
    object_id_2 = "v0.1/demo/bgp/stat/test2"

    # Set the same rate limit for both: 2 requests per minute
    rate_limit = (2, 60)

    with patch("django_auditctl.limit.get_rate_limit", return_value=rate_limit):
        with patch(
            "django_auditctl.limit.ratelimit_cache.get", side_effect=mock_cache_get
        ):
            with patch(
                "django_auditctl.limit.ratelimit_cache.set", side_effect=mock_cache_set
            ):
                # Initially neither should be limited
                assert not is_limited(object_id_1)
                assert not is_limited(object_id_2)

                # Record events for first object ID until it's limited
                # First event
                set_limited(object_id_1)
                assert not is_limited(object_id_1)

                # Second event
                set_limited(object_id_1)
                # After 2 events we've reached the limit (2 per minute)
                assert is_limited(object_id_1)

                # The second object ID should still not be limited
                assert not is_limited(object_id_2)

                # Record one event for the second object ID
                # First event
                set_limited(object_id_2)
                assert not is_limited(object_id_2)

                # First object ID should still be limited
                assert is_limited(object_id_1)

                # Check cache contents to verify separate storage
                cache_key_1 = f"ratelimit:{object_id_1}"
                cache_key_2 = f"ratelimit:{object_id_2}"

                # First object should have 2 timestamps
                assert len(mock_cache[cache_key_1]) == 2

                # Second object should have 1 timestamp
                assert len(mock_cache[cache_key_2]) == 1
