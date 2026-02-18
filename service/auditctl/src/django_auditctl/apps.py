from django.apps import AppConfig


class DjangoAuditctlConfig(AppConfig):
    name = "django_auditctl"
    label = "django_auditctl"

    def ready(self):
        import django_auditctl.signals  # noqa: F401
