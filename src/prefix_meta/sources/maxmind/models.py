from django.db import models
from django.utils.translation import gettext_lazy as _

from prefix_meta.models import Data


class MaxmindLocationData(Data):
    """
    Maxmind Location Data
    """

    location_type = models.CharField(
        choices=(
            ("city", "City"),
            ("country", "Country"),
        ),
        null=False,
        help_text=_("The type of the location data"),
    )
    geoname_id = models.PositiveIntegerField()

    class Meta:
        indexes = [
            models.Index("location_type", name="location_type_idx"),
            models.Index(
                fields=["location_type", "data_ptr"], name="location_compound_idx"
            ),
        ]

    class Config(Data.Config):
        source_name = "maxmind"
        type = "location"

    @classmethod
    def get_prefix_queryset(cls, prefix: str, location_type: str):
        return (
            cls.objects.filter(prefix__net_contains_or_equals=prefix)
            .filter(
                type=cls.config("type"),
                source_name=cls.config("source_name"),
                location_type=location_type,
            )
            .order_by("-date", "prefix")
            .distinct("date", "prefix")
        )


class MaxmindLocationsReferenceData(models.Model):
    """
    Maxmind Locations Reference Data
    Contains all extra location data like
     - country_iso_code, continent_name, continent_code etc.
    """

    geoname_id = models.PositiveIntegerField()
    data = models.JSONField()

    class Meta:
        indexes = [
            models.Index("geoname_id", name="geoname_id_idx"),
        ]
