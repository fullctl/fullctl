STATIC_URL = "/s/test"
PACKAGE_VERSION = "test"
SERVER_EMAIL = "default@localhost"
EMAIL_DEFAULT_FROM = "default@localhost"
EMAIL_NOREPLY = "noreply@localhost"
DEBUG = True
SERVICE_KEY = "dead:beef"
SECURE_SSL_REDIRECT = False
AUTO_USER_TO_ORG = None
AAACTL_URL = "http://localhost"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "stderr": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "": {"handlers": ["stderr"], "level": "DEBUG", "propagate": False},
    },
}
