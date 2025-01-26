from prefix_meta.models import Data


class MaxmindData(Data):
    """
    Meta data returned from Maxmind
    """

    class Meta:
        proxy = True

    class Config(Data.Config):
        source_name = "maxmind"
        type = "location"

    class HandleRef:
        tag = "maxmind_meta_data"

    @classmethod
    def get_prefix_queryset(cls, prefix: str):
        return (
            cls.objects.filter(prefix__net_contains_or_equals=prefix)
            .filter(
                type=cls.config("type"),
                source_name=cls.config("source_name"),
            )
            .order_by("-date", "prefix")
            .distinct("date", "prefix")
        )
