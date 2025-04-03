# Rate Limiting in AuditCTL

## Overview

AuditCTL includes a configurable rate limiting system that allows you to control the frequency of specific event types. This is particularly useful for high-volume events that could potentially overwhelm the system or for implementing throttling on specific API endpoints.

# For Server Administrators

This section covers what you need to know to configure and manage rate limiting using environment variables without modifying code.

## Enabling Rate Limiting

Rate limiting is disabled by default. To enable it:

```bash
# Set this environment variable to enable rate limiting
export EVENT_RATE_LIMIT_ENABLED=True
```

## Available Rate Limit Options

The following environment variables control rate limiting behavior:

| Environment Variable | Default | Description |
|----------------------|---------|-------------|
| `EVENT_RATE_LIMIT_ENABLED` | `False` | Master switch to enable/disable rate limiting |
| `EVENT_RATE_LIMIT_BGP_STAT` | `"1/second"` | Rate limit for BGP statistics events |

Rate limits are specified in the format: `"[count]/[time_unit]"` where:
- `count` is an integer representing the maximum number of events allowed
- `time_unit` is one of: `second`, `minute`, or `hour`

Examples:
- `"1/second"` - Allow 1 event per second
- `"5/minute"` - Allow 5 events per minute
- `"10/hour"` - Allow 10 events per hour

## Redis Configuration

Rate limiting requires Redis. Configure the Redis connection with these environment variables:

| Environment Variable | Description |
|----------------------|-------------|
| `REDIS_HOST` | Redis server hostname |
| `REDIS_PORT` | Redis server port |
| `REDIS_DB` | Redis database number |
| `REDIS_PASSWORD` | Redis password (if required) |

## Administrator Troubleshooting

If you're experiencing unexpected rate limiting behavior:

1. Verify rate limiting is enabled: `EVENT_RATE_LIMIT_ENABLED=True`
2. Check Redis connection parameters
3. Verify rate limit values are appropriate for your traffic patterns
4. Check logs for any rate limit related errors

# For Developers

This section covers implementation details for developers who need to modify code or add new rate limits.

## How Rate Limiting Works

1. When an event is processed, the system checks if it matches any of the patterns defined in the `RATE_LIMIT` dictionary.
2. If a match is found, the system retrieves the corresponding rate limit.
3. The system then checks if the event exceeds the defined rate limit by:
   - Retrieving recent timestamps for the event from the Redis cache
   - Removing timestamps that are outside the time window
   - Counting the remaining timestamps
   - If the count is less than the limit, the event is processed normally
   - If the count equals or exceeds the limit, the event is rate-limited

## Technical Implementation

Rate limiting is implemented in `django_auditctl/limit.py` using:

- Redis cache for storing timestamps of events
- Regular expressions for matching event types
- A dedicated cache configuration called "ratelimit"

The implementation uses these key functions:
- `is_rate_limiting_enabled()` - Checks if rate limiting is enabled
- `get_rate_limit(object_id)` - Determines if a rate limit applies to an object ID
- `is_limited(object_id)` - Checks if an object is currently rate-limited
- `set_limited(object_id)` - Records an event occurrence for rate limiting

When rate limiting is enabled, a Redis cache instance is configured:

```python
if EVENT_RATE_LIMIT_ENABLED:
    CACHES["ratelimit"] = {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}",
        'OPTIONS': {
            'password': REDIS_PASSWORD,
        }
    }
```

## Adding Custom Rate Limits

To add a new rate limit:

1. Define a new setting option in `settings/__init__.py`:

```python
settings_manager.set_option("EVENT_RATE_LIMIT_CUSTOM_EVENT", "5/minute")
```

2. Add the corresponding pattern to the `RATE_LIMIT` dictionary in `django_auditctl/limit.py`:

```python
RATE_LIMIT = {
    r"^v0.\d+\/[^\/]+\/bgp\/stat\/": getattr(
        settings, "EVENT_RATE_LIMIT_BGP_STAT", "99999/second"
    ),
    r"^v0.\d+\/[^\/]+\/custom\/event\/": getattr(
        settings, "EVENT_RATE_LIMIT_CUSTOM_EVENT", "99999/second"
    ),
}
```

3. Make sure your regular expression pattern correctly matches the event IDs you want to rate limit.

4. Add tests in `tests/test_ratelimit.py` to verify your new rate limit works correctly.

## Rate Limit Pattern Matching

Rate limits are applied based on regex pattern matching against event IDs. The current implementation supports event versioning with the pattern `r"^v0.\d+\/[^\/]+\/bgp\/stat\/"`.

# Common Use Cases

- **High Volume BGP Stats**: Limiting BGP statistics to prevent flooding the system during network events
- **API Protection**: Preventing abuse of sensitive API endpoints
- **Resource Intensive Operations**: Limiting operations that consume significant resources 