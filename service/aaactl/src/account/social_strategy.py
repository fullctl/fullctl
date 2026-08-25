"""
Settings strategy that overlays Django settings with values from the
``OAuthConfig`` table.

For ``SOCIAL_AUTH_{SERVICE}_{FIELD}`` lookups where ``{FIELD}`` matches one
of the DB-backed fields below, returns the value from the row whose
``service_id`` equals ``{SERVICE}.lower()``. If no row exists or the field
is empty, falls back to the default Django settings lookup.

A single auth flow triggers ``setting()`` many times per backend (one call
per field, plus retries with the unprefixed name). To avoid 8+ DB hits per
flow, the strategy memoizes ``OAuthConfig`` lookups on the instance —
strategies are constructed per request by ``social_django.utils.load_strategy``
so the cache lifetime is the request.

Wire this in via ``SOCIAL_AUTH_STRATEGY = "account.social_strategy.DBStrategy"``.
"""

import re

from social_django.strategy import DjangoStrategy

# field name in the SOCIAL_AUTH_{SERVICE}_{FIELD} setting -> OAuthConfig attr
_DB_FIELDS = {
    "KEY": "key",
    "SECRET": "secret",
    "TENANT_ID": "tenant_id",
    "AUTHORIZATION_URL": "authorization_url",
    "ACCESS_TOKEN_URL": "access_token_url",
    "PROFILE_URL": "profile_url",
    "ACCESS_TOKEN_METHOD": "access_token_method",
    "DEFAULT_SCOPE": "default_scope",
    "EXTRA_DATA": "extra_data",
}

# longest-first so the alternation prefers ACCESS_TOKEN_URL over ACCESS_TOKEN_*
_FIELD_RE = "|".join(sorted(_DB_FIELDS, key=len, reverse=True))
_SETTING_RE = re.compile(
    rf"^SOCIAL_AUTH_(?P<service>[A-Z0-9_]+)_(?P<field>{_FIELD_RE})$"
)

_MISSING = object()


class DBStrategy(DjangoStrategy):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # service_id -> OAuthConfig | None, populated lazily, scoped to this
        # strategy instance (one per request).
        self._oauth_config_cache = {}

    def _get_oauth_config(self, service_id):
        cached = self._oauth_config_cache.get(service_id, _MISSING)
        if cached is not _MISSING:
            return cached

        from account.models import OAuthConfig

        try:
            config = OAuthConfig.objects.get(service_id=service_id)
        except OAuthConfig.DoesNotExist:
            config = None
        self._oauth_config_cache[service_id] = config
        return config

    def get_setting(self, name):
        match = _SETTING_RE.match(name)
        if match:
            attr = _DB_FIELDS[match.group("field")]
            service_id = match.group("service").lower()
            config = self._get_oauth_config(service_id)
            if config is not None:
                value = getattr(config, attr)
                # Empty values (None, "", [], {}) mean "not set" — fall through
                # so the backend's class-level default or Django settings win.
                if value:
                    return value
        return super().get_setting(name)
