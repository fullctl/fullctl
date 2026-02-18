import secrets

settings_manager.set_option("SERVER_EMAIL", "root@localhost")
settings_manager.set_option(
    "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
)

settings_manager.set_from_env("SECRET_KEY", None)
if not SECRET_KEY:
    settings_manager.print_debug("SECRET_KEY not set, generating an ephemeral one")
    SECRET_KEY = secrets.token_urlsafe(64)

SILENCED_SYSTEM_CHECKS = ["django_recaptcha.recaptcha_test_key_error"]

# random static URL to stop caching
STATIC_URL = f"/s/{secrets.token_urlsafe(1)}/"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
