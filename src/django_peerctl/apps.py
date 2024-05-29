from django.apps import AppConfig
import structlog

log = structlog.get_logger("django")

class DjangoPeerctlConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_peerctl"

    def ready(self):
        import django_peerctl.signals  # noqa

        from django.conf import settings

        # Does this peerctl instance want to use pdbctl as a source
        # of truth for peers and exchanges?
        if not getattr(settings, "PDBCTL_SOT_IX", True):

            # We do not want to use pdbctl as a source of truth
            # so we remove it from the service bridge sources
            # list for sot.InternetExchangeMember

            import fullctl.service_bridge.sot as sot
            import fullctl.service_bridge.pdbctl as pdbctl

            sot.InternetExchangeMember.sources.remove(
                (pdbctl.NetworkIXLan, {})
            )

            sot.InternetExchange.sources.remove(
                (pdbctl.InternetExchange, {})
            )

            def empty_objects(self, *args, **kwargs):
                # empty generator
                return
                yield

            pdbctl.NetworkIXLan.objects = empty_objects
            pdbctl.InternetExchange.objects = empty_objects

            log.info("pdbctl DISABLED as source of truth for InternetExchangeMember and InternetExchange")

        else:
            log.info("pdbctl ENABLED as source of truth for InternetExchangeMember and InternetExchange")

