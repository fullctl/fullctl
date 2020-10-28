from django.apps import AppConfig


class DjangoFullctlConfig(AppConfig):
    name = "django_fullctl"
    label = "django_fullctl"

    def ready(self):
        import fullctl.django.signals
