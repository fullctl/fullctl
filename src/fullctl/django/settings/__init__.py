"""
This file handles the default django settings for fullctl services.

Versioning has been dropped in favor of using separate function names.
"""
import os
import sys
from urllib.parse import urljoin

import confu.util


def print_debug(*args, **kwargs):
    # XXX
    print(*args, **kwargs)


def get_locale_name(code):
    """Gets the readble name for a locale code."""
    language_map = dict(django.conf.global_settings.LANGUAGES)

    # check for exact match
    if code in language_map:
        return language_map[code]

    # try for the language, fall back to just using the code
    language = code.split("-")[0]
    return language_map.get(language, code)


def read_file(name):
    with open(name) as fh:
        return fh.read()


# TODO : add dict access and logging
class SettingsManager(confu.util.SettingsManager):

    # settings manager extensions

    def get(self, name):
        """Get name, raise if not set.
        Should use _DEFAULT_ARG
        """
        #        if key in self.scope:
        return self.scope[name]

    def set_option(self, name, value, envvar_type=None):
        """Return the resulting value after setting."""
        super().set_option(name, value, envvar_type)
        return self.get(name)

    def print_debug(self, *args, **kwargs):
        if DEBUG:
            print(*args, **kwargs)

    def try_include(self, filename):
        """Tries to include another file into current scope."""
        print_debug(f"including {filename}")
        try:
            with open(filename) as f:
                exec(compile(f.read(), filename, "exec"), self.scope)

            print_debug(f"loaded additional settings file '{filename}'")

        except FileNotFoundError:
            print_debug(
                f"additional settings file '{filename}' was not found, skipping"
            )

    def try_include_env(self, suffix=""):
        # look for mainsite/settings/${RELEASE_ENV}.py and load if it exists
        # needs __file__ from caller
        env_file = os.path.join(
            os.path.dirname(__file__), f"{self.get('RELEASE_ENV')}.py"
        )
        settings.try_include(env_file)

    # fullctl helpers #######

    def set_release_env(self):
        """
        Sets release env for django service settings version 1.

        Version is an arbitrary number to define the defaults to allow for ease of service migration.
        """
        # set RELEASE_ENV, usually one of dev, beta, prod, run_tests
        self.set_option("RELEASE_ENV", "dev")
        release_env = self.scope["RELEASE_ENV"]

        # set DEBUG first, print_debug() depends on it
        if release_env == "dev":
            self.set_bool("DEBUG", True)
        else:
            self.set_bool("DEBUG", False)

        if release_env == "prod":
            # we only expose admin on non-production environments
            self.set_bool("EXPOSE_ADMIN", False)
        else:
            self.set_bool("EXPOSE_ADMIN", True)

    def set_default_v1(self):
        """
        Sets default django service settings version 1.

        Version is an arbitrary number to define the defaults to allow for ease of service migration.
        """
        service_tag = self.scope["SERVICE_TAG"]

        # Contact email, from address, support email
        self.set_from_env("SERVER_EMAIL")

        # django secret key
        self.set_from_env("SECRET_KEY")

        # database

        self.set_option("DATABASE_ENGINE", "postgresql_psycopg2")
        self.set_option("DATABASE_HOST", "127.0.0.1")
        self.set_option("DATABASE_PORT", "")
        self.set_option("DATABASE_NAME", service_tag)
        self.set_option("DATABASE_USER", service_tag)
        self.set_option("DATABASE_PASSWORD", "")

        # email

        # default email goes to console
        self.set_option(
            "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
        )
        # TODO EMAIL_SUBJECT_PREFIX = "[{}] ".format(RELEASE_ENV)

        self.set_from_env("EMAIL_HOST")
        self.set_from_env("EMAIL_PORT")
        self.set_from_env("EMAIL_HOST_USER")
        self.set_from_env("EMAIL_HOST_PASSWORD")
        self.set_bool("EMAIL_USE_TLS", True)

        # Application definition

        INSTALLED_APPS = [
            "django.contrib.admin",
            "django.contrib.auth",
            "django.contrib.contenttypes",
            "django.contrib.sessions",
            "django.contrib.messages",
            "django.contrib.staticfiles",
        ]
        self.set_default("INSTALLED_APPS", INSTALLED_APPS)

        MIDDLEWARE = [
            "django.middleware.security.SecurityMiddleware",
            "whitenoise.middleware.WhiteNoiseMiddleware",
            "django.contrib.sessions.middleware.SessionMiddleware",
            "django.middleware.common.CommonMiddleware",
            "django.middleware.csrf.CsrfViewMiddleware",
            "django.contrib.auth.middleware.AuthenticationMiddleware",
            "django.contrib.messages.middleware.MessageMiddleware",
            "django.middleware.clickjacking.XFrameOptionsMiddleware",
            "fullctl.django.middleware.CurrentRequestContext",
        ]
        self.set_default("MIDDLEWARE", MIDDLEWARE)

        self.set_default("ROOT_URLCONF", f"{service_tag}.urls")
        self.set_default("WSGI_APPLICATION", f"{service_tag}.wsgi.application")

        # eval from default.py file
        filename = os.path.join(os.path.dirname(__file__), f"default.py")
        self.try_include(filename)

    def set_default_append(self):
        DEBUG = self.get("DEBUG")
        self.set_option("DEBUG_EMAIL", DEBUG)
        for template in self.get("TEMPLATES"):
            template["OPTIONS"]["debug"] = DEBUG
        # TEMPLATES[0]["OPTIONS"]["debug"] = DEBUG

        # use structlog for logging
        import structlog

        MIDDLEWARE = self.get("MIDDLEWARE")

        MIDDLEWARE += [
            "django_structlog.middlewares.RequestMiddleware",
        ]

        # set these explicitly, not with DEBUG
        DJANGO_LOG_LEVEL = self.set_option("DJANGO_LOG_LEVEL", "INFO")
        FULLCTL_LOG_LEVEL = self.set_option("FULLCTL_LOG_LEVEL", "DEBUG")

        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
            ],
            context_class=structlog.threadlocal.wrap_dict(dict),
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        # logging define extra formatters and handlers for convenience
        LOGGING = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "json": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.processors.JSONRenderer(),
                },
                "color_console": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.dev.ConsoleRenderer(),
                },
                "key_value": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.processors.KeyValueRenderer(
                        key_order=["timestamp", "level", "event", "logger"]
                    ),
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "color_console",
                    "stream": sys.stdout,
                },
                "console_json": {
                    "class": "logging.StreamHandler",
                    "formatter": "json",
                    "stream": sys.stdout,
                },
                "mail_admins": {
                    "class": "django.utils.log.AdminEmailHandler",
                    "level": "ERROR",
                    # plain text by default - HTML is nicer
                    "include_html": True,
                },
            },
            "loggers": {
                "django": {
                    "handlers": ["console_json"],
                    "level": DJANGO_LOG_LEVEL,
                },
                "django_structlog": {
                    "handlers": ["console_json"],
                    "level": FULLCTL_LOG_LEVEL,
                },
            },
        }
        self.set_option("LOGGING", LOGGING)

    def set_service_bridges(self):
        # no default so we error sooner
        self.set_option("AAACTL_HOST", "")
        self.set_option("PDBCTL_HOST", "")
        self.set_option("PEERCTL_HOST", "")
        self.set_option("IXCTL_HOST", "")

    def set_twentyc_oauth(self, AAACTL_HOST=None):
        if not AAACTL_HOST:
            AAACTL_HOST = self.get("AAACTL_HOST")

        self.set_option("OAUTH_TWENTYC_HOST", AAACTL_HOST)
        self.set_option(
            "OAUTH_TWENTYC_ACCESS_TOKEN_URL", f"{AAACTL_HOST}/account/auth/o/token/"
        )
        self.set_option(
            "OAUTH_TWENTYC_AUTHORIZE_URL", f"{AAACTL_HOST}/account/auth/o/authorize/"
        )
        self.set_option(
            "OAUTH_TWENTYC_PROFILE_URL", f"{AAACTL_HOST}/account/auth/o/profile/"
        )

        self.set_option("OAUTH_TWENTYC_KEY", "")
        self.set_option("OAUTH_TWENTYC_SECRET", "")

        self.set_option("SOCIAL_AUTH_TWENTYC_KEY", self.get("OAUTH_TWENTYC_KEY"))
        self.set_option("SOCIAL_AUTH_TWENTYC_SECRET", self.get("OAUTH_TWENTYC_SECRET"))
        self.set_option("SOCIAL_AUTH_REDIRECT_IS_HTTPS", True)

        AUTHENTICATION_BACKENDS = [
            "fullctl.django.social.backends.twentyc.TwentycOAuth2",
            # fall back to local auth
            "django.contrib.auth.backends.ModelBackend",
        ]
        self.set_option("AUTHENTICATION_BACKENDS", AUTHENTICATION_BACKENDS)

        GRAINY_REMOTE = {
            "url_load": urljoin(AAACTL_HOST, "grainy/load/"),
            # "url_get": f"{OAUTH_TWENTYC_HOST}/grainy/get/" + "{}/",
        }
        self.set_option("GRAINY_REMOTE", GRAINY_REMOTE)

        SOCIAL_AUTH_PIPELINE = (
            "social_core.pipeline.social_auth.social_details",
            "social_core.pipeline.social_auth.social_uid",
            "social_core.pipeline.social_auth.social_user",
            "social_core.pipeline.user.get_username",
            "social_core.pipeline.user.create_user",
            "social_core.pipeline.social_auth.associate_user",
            "social_core.pipeline.social_auth.load_extra_data",
            "fullctl.django.social.pipelines.sync_organizations",
            "social_core.pipeline.user.user_details",
        )
        self.set_option("SOCIAL_AUTH_PIPELINE", SOCIAL_AUTH_PIPELINE)

        self.set_option("LOGIN_REDIRECT_URL", "/")
        self.set_option("LOGOUT_REDIRECT_URL", "/login")
        self.set_option("LOGIN_URL", "/login")

    def set_twentyc_service(self, billing_integration=True, propagate_user_fields=True):
        """
        Sets up everything needed for a twentyc service.

        billing_integration
        Toggles billing integration with aaactl, if false, billing checks on api end points will be disabled
        """
        self.set_option("SERVICE_KEY", "")
        self.set_service_bridges()
        self.set_twentyc_oauth()

        # allow propagation of user field changes during oauth process
        # with exception of id fields
        if propagate_user_fields:
            self.set_option("SOCIAL_AUTH_NO_DEFAULT_PROTECTED_USER_FIELDS", True)
            self.set_option("SOCIAL_AUTH_PROTECTED_USER_FIELDS", ("id", "pk"))

        # toggle billing integration with aaactl
        # if false, billing checks on api end points will be disabled
        self.set_bool("BILLING_INTEGRATION", billing_integration)

    def set_languages_docs(self):
        self.set_option("ENABLE_ALL_LANGUAGES", False)

        if ENABLE_ALL_LANGUAGES:
            language_dict = dict(LANGUAGES)
            for locale_path in LOCALE_PATHS:
                for name in os.listdir(locale_path):
                    path = os.path.join(locale_path, name)
                    if not os.path.isdir(os.path.join(path, "LC_MESSAGES")):
                        continue
                    code = name.replace("_", "-").lower()
                    if code not in language_dict:
                        name = _(get_locale_name(code))
                        language_dict[code] = name

            LANGUAGES = sorted(language_dict.items())

        API_DOC_INCLUDES = {}
        API_DOC_PATH = os.path.join(BASE_DIR, "docs", "api")
        for i, j, files in os.walk(API_DOC_PATH):
            for file in files:
                base, ext = os.path.splitext(file)
                if ext == ".md":
                    API_DOC_INCLUDES[base] = os.path.join(API_DOC_PATH, file)
