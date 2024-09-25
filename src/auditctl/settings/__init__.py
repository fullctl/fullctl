import os
import sys  # noqa

from fullctl.django import settings

SERVICE_TAG = "auditctl"

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

# Intialize settings manager with global variable
settings_manager = settings.SettingsManager(globals())
settings_manager.set_release_env()

# look for mainsite/settings/${RELEASE_ENV}.py and load if it exists
env_file = os.path.join(os.path.dirname(__file__), f"{RELEASE_ENV}.py")
settings_manager.try_include(env_file)


# set version, default from /srv/service/etc/VERSION
settings_manager.set_option(
    "PACKAGE_VERSION", settings.read_file(os.path.join(BASE_DIR, "etc/VERSION")).strip()
)

settings_manager.set_default_v1()

# AUDITCTL Base

MIDDLEWARE += ("fullctl.django.middleware.RequestAugmentation",)

INSTALLED_APPS += (
    "dal",
    "dal_select2",
    "django_handleref",
    "django_grainy",
    "rest_framework",
    "social_django",
    "reversion",
    "fullctl.django.apps.DjangoFullctlConfig",
    "django_auditctl.apps.DjangoAuditctlConfig",
)

TEMPLATES[0]["OPTIONS"]["context_processors"] += [
    "social_django.context_processors.backends",
    "social_django.context_processors.login_redirect",
    "fullctl.django.context_processors.account_service",
    "fullctl.django.context_processors.permissions",
    "fullctl.django.context_processors.conf",
]

# Fullctl service integration

settings_manager.set_twentyc_service()

# DJANGO REST FRAMEWORK

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ("fullctl.django.rest.renderers.JSONRenderer",),
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "fullctl.django.rest.authentication.APIKeyAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    # Use hyperlinked styles by default.
    # Only used if the `serializer_class` attribute is not set on a view.
    "DEFAULT_MODEL_SERIALIZER_CLASS": (
        "rest_framework.serializers.HyperlinkedModelSerializer"
    ),
    # Use Django's standard `django.contrib.auth` permissions,
    # or allow read-only access for unauthenticated users.
    # Handle rest of permissioning via django-namespace-perms
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    # FIXME: need to somehow allow different drf settings by app
    "EXCEPTION_HANDLER": "fullctl.django.rest.core.exception_handler",
    "DEFAULT_THROTTLE_RATES": {"email": "1/minute"},
    "DEFAULT_SCHEMA_CLASS": "fullctl.django.rest.api_schema.BaseSchema",
}


# OUTSIDE SERVICES

settings_manager.set_option("GOOGLE_ANALYTICS_ID", "")

# use wss:// for ssl - used by js side to connect
settings_manager.set_option("EVENT_STREAM_URL", "")

# server will bind to this host and port
settings_manager.set_option("EVENT_STREAM_HOST", "0.0.0.0")
settings_manager.set_option("EVENT_STREAM_PORT", 7148)

# Heartbeat interval - how long before an alert is sent - 15 minutes
settings_manager.set_option("HEARTBEAT_EXPECTED_INTERVAL", 60 * 15)

# Heartbeat interval - how long before an alert is sent - 6 minutes for traffic
settings_manager.set_option("HEARTBEAT_EXPECTED_INTERVAL_TRAFFIC", 60 * 6)

# Default max age before events are considered stale and will be pruned
# by the prune_old_auditlog_events management command (if no max_age is provided)
# Default is 90 days (in days)
settings_manager.set_option("EVENT_MAX_AGE", 90)

# FINALIZE

settings_manager.set_default_append()

# look for mainsite/settings/${RELEASE_ENV}_append.py and load if it exists
env_file = os.path.join(os.path.dirname(__file__), f"{RELEASE_ENV}_append.py")
settings_manager.try_include(env_file)

# TODO combine to log summarry to INFO
settings.print_debug(f"loaded settings for version {PACKAGE_VERSION} (DEBUG: {DEBUG})")
