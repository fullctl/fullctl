from django.db import models
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


class PrefixMetaSourceConfig(models.Model):
    """
    Global configuration for available reputation sources.

    Controls which organizations can toggle specific sources on/off based on
    namespace permissions.

    This only controls the organization's ability to toggle the source,
    not whether the organization has access during report generation.
    """

    source = models.CharField(max_length=64, unique=True)

    namespace = models.CharField(max_length=255)

    class Meta:
        db_table = "prefix_meta_source_config"

    class HandleRef:
        tag = "prefix_meta_source_config"

    def __str__(self):
        return f"{self.source} ({self.namespace})"

    def get_namespace_for_org(self, org):
        """Generate the actual namespace for a specific org"""
        return self.namespace.format(org_id=org.id)

    def get_namespace_for_org(self, org):
        """Generate the actual namespace for a specific org"""
        return self.namespace.format(org_id=org.id)


class OrganizationPrefixMetaSource(models.Model):
    """
    Per-organization toggle for individual reputation sources.

    Allows organizations to enable/disable specific sources for all their
    prefix sets (unless overridden at the prefix-set level).
    """

    org = models.ForeignKey(
        "django_fullctl.Organization",
        on_delete=models.CASCADE,
        related_name="prefix_meta_sources",
    )

    source = models.ForeignKey(
        PrefixMetaSourceConfig, on_delete=models.CASCADE, to_field="source"
    )

    status = models.CharField(
        max_length=16,
        choices=[
            ("ok", "Enabled"),
            ("disabled", "Disabled"),
        ],
        default="ok",
    )

    class Meta:
        db_table = "org_prefix_meta_source"
        unique_together = [["org", "source"]]

    class HandleRef:
        tag = "org_prefix_meta_source"

    def __str__(self):
        return f"{self.org.name} - {self.source}: {self.status}"

    @property
    def namespace(self):
        """Get the formatted namespace for this org's source"""
        return self.source.get_namespace_for_org(self.org)


class PrefixSetPrefixMetaSource(models.Model):
    """
    Per-prefix-set toggle for individual reputation sources.

    Allows fine-grained control at the prefix-set level, overriding
    both global defaults and organization-level settings.
    """

    prefix_set = models.ForeignKey(
        "django_prefixctl.PrefixSet",
        on_delete=models.CASCADE,
        related_name="prefix_meta_sources",
    )

    source = models.ForeignKey(
        PrefixMetaSourceConfig, on_delete=models.CASCADE, to_field="source"
    )

    status = models.CharField(
        max_length=16,
        choices=[
            ("ok", "Enabled"),
            ("disabled", "Disabled"),
        ],
        default="ok",
    )

    class Meta:
        db_table = "prefixset_prefix_meta_source"
        unique_together = [["prefix_set", "source"]]

    class HandleRef:
        tag = "prefixset_prefix_meta_source"

    def __str__(self):
        return f"{self.prefix_set.name} - {self.source}: {self.status}"
