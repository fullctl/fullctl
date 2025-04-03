"""
Rate limit incoming events based on matching the event object id.
Supports rate limits specified as "N/second", "N/minute", or "N/hour".
"""

from django.utils import timezone
import re
from django.core.cache import caches
from django.conf import settings
import json
import time

__all__ = [
    "get_rate_limit",
    "is_limited",
    "set_limited",
]

# Rate limits are specified as strings like "1/second", "5/minute", "10/hour"
RATE_LIMIT = {
    r"^v0.1\/[^\/]+\/bgp\/stat\/": getattr(
        settings, "EVENT_RATE_LIMIT_BGP_STAT", "99999/second"
    ),
}

# Time window multipliers in seconds
TIME_WINDOWS = {
    "second": 1,
    "minute": 60,
    "hour": 3600,
}


def is_rate_limiting_enabled():
    """Check if rate limiting is enabled in settings."""
    return getattr(settings, "EVENT_RATE_LIMIT_ENABLED", False)


# Get the dedicated ratelimit cache
def get_ratelimit_cache():
    """Get the dedicated rate limit cache."""
    if not is_rate_limiting_enabled():
        return None

    try:
        return caches["ratelimit"]
    except Exception:
        # Fall back to default cache if ratelimit cache is not configured
        from django.core.cache import cache

        return cache


# Cache instance
ratelimit_cache = get_ratelimit_cache()


def parse_rate_limit(rate_str):
    """
    Parse a rate limit string like "1/second" into a tuple of (count, window_in_seconds).

    Args:
        rate_str: A string in the format "N/window" where window is one of
                 "second", "minute", or "hour".

    Returns:
        tuple: (count, window_in_seconds)
    """
    try:
        count, window = rate_str.split("/")
        count = int(count)

        if window not in TIME_WINDOWS:
            # Default to seconds if window is not recognized
            window = "second"

        return (count, TIME_WINDOWS[window])
    except (ValueError, AttributeError):
        raise ValueError(f"Invalid rate limit string: {rate_str}")


def get_rate_limit(object_id: str) -> tuple:
    """
    Get the rate limit for an object ID.

    Args:
        object_id: The object ID to check against patterns.

    Returns:
        tuple: (count, window_in_seconds) or None if no rate limit applies.
    """
    if not is_rate_limiting_enabled():
        return None

    for pattern, limit in RATE_LIMIT.items():
        if re.match(pattern, object_id):
            return parse_rate_limit(limit)

    return None


def clean_old_timestamps(object_id: str, window_seconds: int, timestamps: list) -> list:
    """
    Filter out timestamps that are outside the current time window.

    Args:
        object_id: The object ID to clean timestamps for.
        window_seconds: The time window in seconds.
        timestamps: List of timestamps to clean.

    Returns:
        list: Filtered list of timestamps within the time window.
    """
    now = time.time()
    min_time = now - window_seconds

    # Keep only timestamps that are within the window
    return [ts for ts in timestamps if ts >= min_time]


def is_limited(object_id: str) -> bool:
    """
    Check if an object ID is currently rate-limited.

    Args:
        object_id: The object ID to check.

    Returns:
        bool: True if the object is rate-limited, False otherwise.
    """
    if not is_rate_limiting_enabled():
        return False

    rate_limit = get_rate_limit(object_id)

    if rate_limit is None:
        return False

    count_limit, window_seconds = rate_limit

    if not ratelimit_cache:
        return False

    cache_key = f"ratelimit:{object_id}"
    timestamps = ratelimit_cache.get(cache_key, [])

    # Clean up old timestamps
    valid_timestamps = clean_old_timestamps(object_id, window_seconds, timestamps)

    # If the valid timestamps are different from the original, update the cache
    if len(valid_timestamps) != len(timestamps):
        # Only update if there are valid timestamps, otherwise just let it expire
        if valid_timestamps:
            ratelimit_cache.set(cache_key, valid_timestamps, timeout=window_seconds * 2)

    # If we have fewer timestamps than the count limit, we're not limited
    return len(valid_timestamps) >= count_limit


def set_limited(object_id: str):
    """
    Record an event for an object ID for rate limiting purposes.

    Args:
        object_id: The object ID to record an event for.

    Returns:
        bool: True if the rate limit was applied, False if no rate limit applies.
    """
    if not is_rate_limiting_enabled():
        return False

    rate_limit = get_rate_limit(object_id)

    if rate_limit is None:
        return False

    _, window_seconds = rate_limit

    if not ratelimit_cache:
        return False

    cache_key = f"ratelimit:{object_id}"
    timestamps = ratelimit_cache.get(cache_key, [])

    # Clean up old timestamps
    valid_timestamps = clean_old_timestamps(object_id, window_seconds, timestamps)

    # Add the current timestamp
    now = time.time()
    valid_timestamps.append(now)

    # Store updated timestamps with appropriate timeout
    ratelimit_cache.set(cache_key, valid_timestamps, timeout=window_seconds * 2)

    return True
