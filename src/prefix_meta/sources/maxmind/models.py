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

    class Config(Data.Config):
        source_name = "maxmind"
        type = "location"

    @classmethod
    def get_prefix_queryset(cls, prefix, location_type):
        return (
            super()
            .get_prefix_queryset(prefix)
            .filter(
                type=cls.config("type"),
                source_name=cls.config("source_name"),
                location_type=location_type,
            )
        )


class MaxmindLocationsReferenceData(models.Model):
    """
    Maxmind Locations Reference Data
    Contains all extra location data like
     - country_iso_code, continent_name, continent_code etc.
    """

    geoname_id = models.PositiveIntegerField()
    data = models.JSONField()
