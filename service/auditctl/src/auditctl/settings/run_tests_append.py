EVENT_RATE_LIMIT_ENABLED = True

CACHES["ratelimit"] = {
    "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
}
