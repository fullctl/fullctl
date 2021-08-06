from django.apps import AppConfig


class DjangoFullctlConfig(AppConfig):
    name = "fullctl.django"
    label = "django_fullctl"
    default_auto_field = "django.db.models.AutoField"

    def ready(self):
        import fullctl.django.signals  # noqa: F401
