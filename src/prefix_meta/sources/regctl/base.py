import prefix_meta.models as prefix_meta

from fullctl.service_bridge.client import url_join

from django.conf import settings
from rdap.schema.normalized import IPNetwork

__all__ = [
    "RegCtlData",
    "RegCtlRequest",
]


class RegCtlData(prefix_meta.Data):
    class Meta:
        proxy = True

    class Config(prefix_meta.Data.Config):
        period = 86400
        source_name = "regctl"
        type = "regctl"

    class HandleRef:
        tag = "regctl_meta_data"

    @property
    def rdap_object(self) -> IPNetwork:
        """
        Returns rdap normalized IPNetwork object

        See rdap library for more information
        """
        return IPNetwork(**self.data)

    @classmethod
    def get_prefix_queryset(cls, prefix):
        return (
            super()
            .get_prefix_queryset(prefix)
            .filter(type=cls.config("type"), source_name=cls.config("source_name"))
        )


class RegCtlRequest(prefix_meta.Request):
    class Meta:
        proxy = True

    class Config(prefix_meta.Request.Config):
        max_prefixlen_4 = 1
        max_prefixlen_6 = 1
        min_prefixlen_4 = 32
        min_predixlen_6 = 128

        cache_expiry = 86400

        regctl_path = None

        meta_data_cls = RegCtlData
        source_name = "regctl"

    @classmethod
    def target_to_url(cls, target):
        if not settings.REGCTL_URL:
            raise ValueError("REGCTL_URL is not set in settings")

        return url_join(settings.REGCTL_URL, "ip", str(target)).rstrip("/")
