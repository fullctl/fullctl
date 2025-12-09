from django.apps import AppConfig


class DjangoDevicectlConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_devicectl"

    def ready(self):
        from django.conf import settings  # noqa

        # TODO: better way to initialize nautobot definitions?

        if getattr(settings, "NAUTOBOT_URL", None):
            import django_devicectl.nautobot  # noqa

        import django_devicectl.signals  # noqa
