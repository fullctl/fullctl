import os
import sys  # noqa

from fullctl.django import settings

SERVICE_TAG = "devicectl"

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

# IXCTL Base

MIDDLEWARE += ("fullctl.django.middleware.RequestAugmentation",)

INSTALLED_APPS += (
    "dal",
    "dal_select2",
    "django_handleref",
    "django_grainy",
    "rest_framework",
    "social_django",
    "reversion",
    "netfields",
    "fullctl.django.apps.DjangoFullctlConfig",
    "django_devicectl.apps.DjangoDevicectlConfig",
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

# PEERINGDB

TABLE_PREFIX = "peeringdb_"
ABSTRACT_ONLY = False

# add user defined iso code for Kosovo
COUNTRIES_OVERRIDE = {
    "XK": "Kosovo",
}

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

# SERVICE BRIDGE MAPPING

settings_manager.set_option("SERVICE_BRIDGE_REF_DEVICE", "")
settings_manager.set_option("SERVICE_BRIDGE_REF_VIRTUAL_PORT", "")
settings_manager.set_option("SERVICE_BRIDGE_REF_IP", "")
settings_manager.set_option("SERVICE_BRIDGE_REF_PORT_INFO", "")
settings_manager.set_option(
    "SERVICE_BRIDGE_REF_FACILITY", "fullctl.service_bridge.pdbctl.Facility"
)
settings_manager.set_option(
    "SERVICE_BRIDGE_REF_EVENT", "fullctl.service_bridge.auditctl.Event"
)

# Whitelist of settings the SPA is allowed to read via GET /api/env/{org}/.
# Keys are dotted output paths in the response; values are Django settings
# names. See fullctl.django.rest.views.env for the serialization rules.
API_ENV_WHITELIST = {
    "sot.device": "SERVICE_BRIDGE_REF_DEVICE",
}

# OUTSIDE SERVICES

settings_manager.set_option("GOOGLE_ANALYTICS_ID", "")

settings_manager.set_option("NAUTOBOT_URL", "")
settings_manager.set_option("NAUTOBOT_TOKEN", "")
settings_manager.set_option("NAUTOBOT_DEVICE_ROLE", ["Edge Router"])
settings_manager.set_option("NAUTOBOT_INTERFACE_PHYSICAL", ["sfp"])

# FINALIZE

settings_manager.set_default_append()

# look for mainsite/settings/${RELEASE_ENV}_append.py and load if it exists
env_file = os.path.join(os.path.dirname(__file__), f"{RELEASE_ENV}_append.py")
settings_manager.try_include(env_file)

# TODO combine to log summarry to INFO
settings.print_debug(f"loaded settings for version {PACKAGE_VERSION} (DEBUG: {DEBUG})")


settings_manager.set_option("PREFIXCTL_URL", "")
settings_manager.set_option("PEERCTL_URL", "")
settings_manager.set_option("AUDITCTL_URL", "")


settings_manager.set_option("GRAPHS_PATH", "../graphs")
settings_manager.set_option("GRAPHS_URL", "/graphs")
settings_manager.set_option("GRAPHS_RRD_ENABLED", True)
settings_manager.set_option("MRTG_GRACE_MULTIPLIER", 5)

# when are referee reports discarded (seconds, default=30 days)
settings_manager.set_option("REFEREE_REPORT_MAX_AGE", 86400 * 30)

# when are old bgp stats discarded (seconds, default=10 minutes)
settings_manager.set_option("PHYSICAL_PORT_STATS_BGP_STALE_AFTER", 600)
