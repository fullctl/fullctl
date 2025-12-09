from django.apps import AppConfig


class BillingConfig(AppConfig):
    name = "billing"

    def ready(self):
        import billing.signals  # noqa: F401
        import billing.tasks  # noqa: F401
