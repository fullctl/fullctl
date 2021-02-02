from django.apps import AppConfig


class DjangoFullctlConfig(AppConfig):
    name = "fullctl.django"
    label = "django_fullctl"

    def ready(self):
        import fullctl.django.signals  # noqa: F401
