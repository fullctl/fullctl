try:
    from django.conf import settings

    DEFAULT_SERVICE_KEY = settings.SERVICE_KEY
except ImportError:
    DEFAULT_SERVICE_KEY = ""

from fullctl.service_bridge.client import Bridge, DataObject, url_join

CACHE = {}


class AuditctlEntity(DataObject):
    description = "AuditCtl Object"
    source = "auditctl"


class Auditctl(Bridge):

    """
    Service bridge to auditctl for data
    retrieval
    """

    class Meta:
        service = "auditctl"
        ref_tag = "base"
        data_object_cls = AuditctlEntity

    def __init__(self, key=None, org=None, **kwargs):
        if not key:
            key = DEFAULT_SERVICE_KEY

        kwargs.setdefault("cache_duration", 10)
        kwargs.setdefault("cache", CACHE)

        super().__init__(settings.AUDITCTL_URL, key, org, **kwargs)
        self.url = url_join(self.url, "service-bridge/")


class Event(Auditctl):
    class Meta(Auditctl.Meta):
        ref_tag = "event"
