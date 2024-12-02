SERVER_EMAIL = "test@localhost"
STATIC_URL = "/s/test"
PACKAGE_VERSION = "test"
DEBUG = True
SERVICE_KEY = "dead:beef"
SECURE_SSL_REDIRECT = False

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
