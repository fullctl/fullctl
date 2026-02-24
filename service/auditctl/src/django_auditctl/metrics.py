import pydantic
from django_auditctl.models.auditctl import Event

__all__ = [
    "Metric",
    "MetricsMixin",
    "MetricsMultiComponentMixin",
    "MetricsSelectiveComponentMixin",
    "ComponentTags",
]


class Metric(pydantic.BaseModel):
    name: str
    fields: dict
    tags: dict = pydantic.Field(default_factory=dict)


class ComponentTags(pydantic.BaseModel):
    kind: str | None = None
    tags: list[str]


class ComponentFields(pydantic.BaseModel):
    kind: str | None = None
    fields: list[str]


class MetricsMixin:
    @classmethod
    def metric_name(cls) -> str:
        """
        Overrideable class method to determine the name of the metric.
        """

        return cls.__name__.lower()

    @classmethod
    def metrics_enabled(cls) -> bool:
        """
        Overrideable class method to determine if metrics
        should be emitted for the model.
        """

        return True

    @classmethod
    def metric_tags(cls) -> list[ComponentTags] | list[str]:
        """
        Overrideable class method to return a list of `ComponentTags` instances

        This is used to collect tags from the event data into the metric.
        """
        return []

    @classmethod
    def metric_fields(cls) -> list[ComponentFields] | list[str]:
        """
        Overrideable class method to return a list of `ComponentFields` instances

        This is used to collect metric fields from the event data into the metric.
        """

        return []

    @classmethod
    def get_event_data(cls, event: Event) -> pydantic.BaseModel | None:
        """
        Overrideable class method to return the data from the event
        that should be used to generate the metrics.
        """

        return None

    @classmethod
    def get_metric_fields_and_tags(cls, event: Event) -> Metric | list[Metric] | None:
        """
        Overrideable method to return a `MetricsMeta` instance with
        fields and tags for the model.

        Can return a single `MetricsMeta` instance, a list of `MetricsMeta`
        instances, or `None` if no metrics should be emitted.
        """

        tags = {
            "ctl_object_id": event.object_id,
            "ctl_org_id": event.org_id,
        }
        # metrics are numbers, so it needs to be converted
        # ok = 0, error = 1

        int_status = 0 if event.status == "ok" else 1

        fields = {"status": int_status}
        return Metric(name=cls.metric_name(), fields=fields, tags=tags)

    @classmethod
    def collect_component_data(cls, metric: Metric, component: pydantic.BaseModel):
        """
        Collects data from a component and adds it to the metric.
        """

        all_component_tags = cls.metric_tags()
        if all_component_tags and isinstance(all_component_tags[0], str):
            all_component_tags = [ComponentTags(kind=None, tags=all_component_tags)]

        all_component_fields = cls.metric_fields()
        if all_component_fields and isinstance(all_component_fields[0], str):
            all_component_fields = [
                ComponentFields(kind=None, fields=all_component_fields)
            ]

        for component_tags in all_component_tags:
            if component_tags.kind != getattr(component, "kind", None):
                continue

            prefix = f"ctl_{component_tags.kind}_" if component_tags.kind else "ctl_"

            for name in component_tags.tags:

                if component_tags.kind == name:
                    prefix = "ctl_"

                metric.tags[f"{prefix}{name}"] = getattr(component, name)

        for component_fields in all_component_fields:
            if component_fields.kind != getattr(component, "kind", None):
                continue
            for name in component_fields.fields:
                metric.fields[name] = getattr(component, name)


class MetricsSelectiveComponentMixin(MetricsMixin):
    """
    Used for event data that stores a list of distinct components, where each component
    describes a different part of the same event.

    Metric tags and fields will be collected from all components in the event data,
    based on the `metric_tags` and `metric_fields` methods.
    """

    @classmethod
    def get_metric_fields_and_tags(cls, event: Event) -> Metric | list[Metric] | None:

        # base status metric
        metric = super().get_metric_fields_and_tags(event)

        event_data = cls.get_event_data(event)

        if not event_data:
            return metric

        # collect component data into the same metric
        for component in event_data.components:
            cls.collect_component_data(metric, component)

        return metric


class MetricsMultiComponentMixin(MetricsMixin):
    """
    Used for event data that stores a list of distinct components, where each component
    is its own metric.

    Metric tags and fields will be collected from all components in the event data,
    based on the `metric_tags` and `metric_fields` methods
    """

    @classmethod
    def get_metric_fields_and_tags(cls, event: Event) -> Metric | list[Metric] | None:

        event_data = cls.get_event_data(event)
        if not event_data:
            return super().get_metric_fields_and_tags(event)

        # status metric
        metrics = [super().get_metric_fields_and_tags(event)]

        # metric per component
        for component in event_data.components:
            metric = Metric(
                name=cls.metric_name(), tags=metrics[0].tags.copy(), fields={}
            )

            cls.collect_component_data(metric, component)
            metrics.append(metric)

        return metrics
