from prefix_meta.models import Data


class PrefixmetadData(Data):
    """
    Meta data returned from Prefixmetad
    """

    class Meta:
        proxy = True

    class Config(Data.Config):
        source_name = "prefixmetad"
        type = "meta_data"

    class HandleRef:
        tag = "prefixmetad_meta_data"

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

    @property
    def dynamic_data(self) -> dict:
        if getattr(self, "_dynamic_data", None):
            return self._dynamic_data

        data = {}
        locations = self.data.get("locations", [])
        for location in locations:
            location_data = location.get("data", {})
            location_source_name = location.get("source_name")
            data[f"{location_source_name}_city"] = location_data.get("city", {}).get(
                "name", None
            )
            data[f"{location_source_name}_country"] = location_data.get(
                "country", {}
            ).get("country_iso_code", None)

        self._dynamic_data = data
        return self._dynamic_data

    @property
    def dynamic_data_columns(self):
        if getattr(self, "_dynamic_data_columns", None):
            return self._dynamic_data_columns
        self._dynamic_data_columns = [
            column_name for column_name in self.dynamic_data.keys()
        ]
        return self._dynamic_data_columns
