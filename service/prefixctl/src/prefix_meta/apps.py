from django.apps import AppConfig


class PrefixMetaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "prefix_meta"

    def ready(self):
        import prefix_meta.rest.views  # noqa
        import prefix_meta.settings  # noqa
        from django.conf import settings  # noqa

        settings.FULLCTL_ADDON_URLS.append(("prefix_meta.urls", "prefix-meta"))
