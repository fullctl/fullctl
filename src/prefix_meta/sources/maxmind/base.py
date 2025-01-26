import structlog
from django.conf import settings
from .models import MaxmindData
from prefix_meta.models import Request

log = structlog.get_logger("django")


class MaxmindRequest(Request):
    """
    Handles requests and request caching to the API

    Needs `MAXMIND_URL` specified in settings
    """

    class Meta:
        proxy = True

    class Config(Request.Config):
        source_name = "maxmind"
        api_url = f"{settings.MAXMIND_URL}/check/maxmind"
        meta_data_cls = MaxmindData

    class HandleRef:
        tag = "maxmind_request"

    @classmethod
    def target_to_url(cls, target):
        return f"{cls.config('api_url')}/check/maxmind/{target}"

    @classmethod
    def send(cls, target):
        url = cls.target_to_url(target)

        log.debug("maxmind", requesting=url, target=target)
        _resp = cls.send_request(target)

        return cls.process(target, url, 200, lambda: _resp.json())
