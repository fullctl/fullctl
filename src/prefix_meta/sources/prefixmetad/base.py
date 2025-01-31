import structlog
from .models import PrefixmetadData
from prefix_meta.models import Request

log = structlog.get_logger("django")


class PrefixmetadRequest(Request):
    """
    Handles requests and request caching to the API

    Needs `PREFIXMETAD_URL` specified in settings
    """

    class Meta:
        proxy = True

    class Config(Request.Config):
        source_name = "prefixmetad"
        api_url = ""
        meta_data_cls = PrefixmetadData

    class HandleRef:
        tag = "prefixmetad_request"

    @classmethod
    def target_to_url(cls, target):
        return f"{cls.config('api_url')}/check/{target}"

    @classmethod
    def send(cls, target):
        url = cls.target_to_url(target)

        log.debug("prefixmetad", requesting=url, target=target)
        _resp = cls.send_request(url)

        return cls.process(target, url, 200, lambda: _resp.json())
