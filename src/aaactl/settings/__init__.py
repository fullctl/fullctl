import os
import sys  # noqa

from django.utils.translation import gettext_lazy as _  # noqa
from fullctl.django import settings

SERVICE_TAG = "aaactl"

# Build paths inside the project like this: os.path.join(BASE_DIR, ...)
# project base (/srv/service)
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


# Keys

settings_manager.set_from_env("SOCIAL_AUTH_GOOGLE_OAUTH2_KEY")
settings_manager.set_from_env("SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET")
settings_manager.set_from_env("SOCIAL_AUTH_PEERINGDB_KEY")
settings_manager.set_from_env("SOCIAL_AUTH_PEERINGDB_SECRET")
settings_manager.set_from_env("SOCIAL_AUTH_OKTA_OAUTH2_KEY")
settings_manager.set_from_env("SOCIAL_AUTH_OKTA_OAUTH2_SECRET")
settings_manager.set_from_env("SOCIAL_AUTH_OKTA_OAUTH2_API_URL")

settings_manager.set_from_env("SOCIAL_AUTH_OKTA_OPENIDCONNECT_KEY")
settings_manager.set_from_env("SOCIAL_AUTH_OKTA_OPENIDCONNECT_SECRET")
settings_manager.set_from_env("SOCIAL_AUTH_OKTA_OPENIDCONNECT_API_URL")


settings_manager.set_option("RECAPTCHA_PUBLIC_KEY", "...")
settings_manager.set_option("RECAPTCHA_SECRET_KEY", "...")

settings_manager.set_from_env("STRIPE_PUBLIC_KEY")
settings_manager.set_from_env("STRIPE_SECRET_KEY")

# TODO - normalize to either use the host or not (preferably not)
LOGIN_URL = "/account/auth/login/"
LOGIN_REDIRECT_URL = "/account"

# hard overwrite MIDDLEWARE, since ordering here is important
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "oauth2_provider.middleware.OAuth2TokenMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "fullctl.django.middleware.CurrentRequestContext",
    "account.middleware.Impersonation",
    "account.middleware.RequestAugmentation",
    "account.middleware.OAuthLoginError",
]

INSTALLED_APPS += (
    # base
    "django.contrib.sites",
    "django_grainy",
    "reversion",
    "django_recaptcha",
    "django_handleref",
    "rest_framework",
    "rest_framework_simplejwt",
    # rendering
    "crispy_forms",
    "crispy_bootstrap5",
    # phonenumbers
    "phonenumber_field",
    # oauth
    "social_django",
    # aaactl apps
    "whitelabel_fullctl",
    "common",
    "account",
    "billing",
    "applications",
    "fullctl.django.apps.DjangoFullctlConfig",
)

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

TEMPLATES[0]["OPTIONS"]["context_processors"] += [
    "account.context_processors.permissions",
    "account.context_processors.info",
    "fullctl.django.context_processors.conf",
]


settings_manager.set_option("GOOGLE_ANALYTICS_ID", "")
settings_manager.set_option("CLOUDFLARE_ANALYTICS_ID", "")

# Billing integration

settings_manager.set_option("BILLING_ENV", "test")
settings_manager.set_option("BILLING_AGREEMENT_NAME", "aaactl")
BILLING_AGREEMENT_DESCRIPTION = BILLING_AGREEMENT_NAME
BILLING_COMPONENTS = ["fullctl.prefixctl"]
BILLING_HANDLERS = ["billing.product_handlers.fullctl.PrefixCtlPrefixes"]
BILLING_PROCESSORS = ["billing.payment_processors.stripe.Stripe"]
BILLING_DEFAULT_CURRENCY = "USD"


# Auth

AUTHENTICATION_BACKENDS = [
    # add to support unix crypt
    # "django_aaactl.backends.UnixCryptBackend",
    "account.backends.EmailOrUsernameModelBackend",
    "django_grainy.backends.GrainyBackend",
]
VALIDATE_PASSWORD_LENGTH = 8

# OAUTH PROVIDER

INSTALLED_APPS += ["oauth2_provider"]

# MIDDLEWARE for OAuth set above for ordering

AUTHENTICATION_BACKENDS = [
    "oauth2_provider.backends.OAuth2Backend"
] + AUTHENTICATION_BACKENDS

DEFAULT_SCOPES = ["email", "profile", "peeringdb"]

settings_manager.set_list("CORS_ALLOWED_ORIGINS", [], envvar_element_type=str)
settings_manager.set_list("FRONTEND_ORIGINS", [], envvar_element_type=str)

OAUTH2_PROVIDER = {
    "SCOPES": {
        "profile": "user profile",
        "email": "email address",
        "api_keys": "20c api keys",
        "provider:peeringdb": "peeringdb entity associations",
    },
    "ALLOWED_REDIRECT_URI_SCHEMES": ["https"],
    "REQUEST_APPROVAL_PROMPT": "auto",
    "PKCE_REQUIRED": False,
}

settings_manager.set_option(
    "OAUTH2_PROVIDER_APPLICATION_MODEL", "oauth2_provider.Application"
)

# SOCIAL AUTH

SOCIAL_AUTH_REDIRECT_IS_HTTPS = True

# Supported backends

settings_manager.set_option("SOCIAL_AUTH_GOOGLE_OAUTH2_ENABLED", True)
settings_manager.set_option("SOCIAL_AUTH_PEERINGDB_ENABLED", True)
settings_manager.set_option("SOCIAL_AUTH_OKTA_OPENIDCONNECT_ENABLED", True)

if SOCIAL_AUTH_PEERINGDB_ENABLED:
    AUTHENTICATION_BACKENDS.insert(
        0, "account.social_backends.peeringdb.PeeringDBOAuth2"
    )

if SOCIAL_AUTH_OKTA_OPENIDCONNECT_ENABLED:
    AUTHENTICATION_BACKENDS.insert(
        0, "social_core.backends.okta_openidconnect.OktaOpenIdConnect"
    )

if SOCIAL_AUTH_GOOGLE_OAUTH2_ENABLED:
    AUTHENTICATION_BACKENDS.insert(0, "social_core.backends.google.GoogleOAuth2")

SOCIAL_AUTH_PIPELINE = (
    "social_core.pipeline.social_auth.social_details",
    "social_core.pipeline.social_auth.social_uid",
    "social_core.pipeline.social_auth.social_user",
    "account.social_backends.pipelines.get_username",
    "social_core.pipeline.social_auth.associate_by_email",
    "social_core.pipeline.user.create_user",
    "social_core.pipeline.social_auth.associate_user",
    "social_core.pipeline.social_auth.load_extra_data",
    "account.social_backends.pipelines.sync_peeringdb",
    "social_core.pipeline.user.user_details",
    "account.social_backends.pipelines.auto_confirm_email",
)

# We are using postgres so make use of postgres json field

SOCIAL_AUTH_POSTGRES_JSONFIELD = True

# Allow password login

settings_manager.set_option("PASSWORD_LOGIN_ENABLED", True)

# Template Context processors

TEMPLATES[0]["OPTIONS"]["context_processors"] += [
    "social_django.context_processors.backends",
    "social_django.context_processors.login_redirect",
]

# BACKEND: PeeringDB

settings_manager.set_option("PDB_ENDPOINT", "https://auth.peeringdb.com")
PDB_OAUTH_ACCESS_TOKEN_URL = f"{PDB_ENDPOINT}/oauth2/token/"
PDB_OAUTH_AUTHORIZE_URL = f"{PDB_ENDPOINT}/oauth2/authorize/"
PDB_OAUTH_PROFILE_URL = f"{PDB_ENDPOINT}/profile/v1"


# django rest framework

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["common.rest.JSONRenderer"],
    "DEFAULT_AUTHENTICATION_CLASSES": (
        #        'rest_framework.authentication.BasicAuthentication',
        "account.rest.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ),
    # Use hyperlinked styles by default.
    # Only used if the `serializer_class` attribute is not set on a view.
    "DEFAULT_MODEL_SERIALIZER_CLASS": "rest_framework.serializers.HyperlinkedModelSerializer",
    # Use Django's standard `django.contrib.auth` permissions,
    # or allow read-only access for unauthenticated users.
    # Handle rest of permissioning via django-namespace-perms
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    # FIXME: need to somehow allow different drf settings by app
    "EXCEPTION_HANDLER": "common.rest.exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.ScopedRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "invite": "5/minute",
        "resend_email": "5/minute",
        "password_reset": "5/minute",
    },
}

settings_manager.set_default_append()

settings_manager.set_from_env("AAACTL_URL")
settings_manager.set_from_env("IXCTL_URL")


if "AAACTL_URL" not in globals():
    raise ValueError(
        "AAACTL_URL needs to specified in .env as it is used to construct urls used for email confirmations and invites"
    )

# misc aaactl settings
# email to notify new sign-ups to
settings_manager.set_option("SIGNUP_NOTIFICATION_EMAIL", SERVER_EMAIL)

# global toggle email confirmation
settings_manager.set_option("ENABLE_EMAIL_CONFIRMATION", True)

# automatic email confirm on oauath
settings_manager.set_option("CONFIRM_EMAIL_ON_OAUTH", True)

# add new users to this org (needs to be org slug)
settings_manager.set_option("AUTO_USER_TO_ORG", None, str)

# expiry for invite links (days)
settings_manager.set_option("INVITE_EXPIRY", 3)

# look for mainsite/settings/${RELEASE_ENV}_append.py and load if it exists
env_file = os.path.join(os.path.dirname(__file__), f"{RELEASE_ENV}_append.py")
settings_manager.try_include(env_file)

# TODO combine to log summarry to INFO
# add BILLING_ENV
settings.print_debug(f"loaded settings for version {PACKAGE_VERSION} (DEBUG: {DEBUG})")

# support settings
settings_manager.set_support()

settings_manager.set_option("SERVICE_KEY", "")

# origins that are allowed to POST to the anonymous contact backend
# using cross server requests
#
# fullctl services do NOT need to be on this list to use their
# feature request and support contact forms, as those use the service bridge

settings_manager.set_option("CONTACT_ALLOWED_ORIGINS", settings.exposed_list())

settings_manager.set_option("BRANDING_ORG", "")

settings_manager.set_option("ENABLE_ACCOUNT_REGISTRATION", True)