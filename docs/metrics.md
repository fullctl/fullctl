# Tracking event metrics

## Setup timeseries db 

### Environment variables

```
TIMESERIES_DB_URL=http://victoriametrics:8428
TIMESERIES_DB_USER=fullctl
TIMESERIES_DB_PASSWORD=...
```

### Other Relevant settings

- `EVENT_METRICS_ENABLED` - Global off switch for metric collection
- `EVENT_METRIC_PREFIX` - Prefix for metric measurement names (defaults to `auditctl_`)

## Developer notes

Metric data generation is controlled through the event data schemas in `src/django_auditctl/schema.py`

There are multiple class methods that are used to control and generate metric data on a per event basis:

### metrics_enabled

This method is used to determine if metric data should be generated for a given event. It should return a boolean value.

While a default implementation is provided, you can override it if it needs to be more complex, or if you simply want to disable metrics for a given event.

```python
class MyEvent(EventData):
    @classmethod
    def metrics_enabled(cls) -> bool:
        return False
```

### metric_name

This method is used to determine part of the measurement name for the metric data. It should return a string.

It defaults to lower case of the event class name. You can override it if you want to use a different name.

```python
class MyEvent(EventData):
    @classmethod
    def metric_name(cls) -> str:
        return "my_event"
```

### metric_fields

This method is used to determine the fields that should be included in the metric data. It should return a list of strings or a list of ComponentFields instances.

It defaults to an empty list. You can override it if you want to include additional fields.

A `field` represents a metric value that can be aggregated over time. It is a string that represents the name of the field.

Fields need to exists in one of the components sent with the event. If the field does not exist, it will be ignored.

```python
class MyEvent(EventData):
    @classmethod
    def metric_fields(cls) -> list[str]:
        # will add a metric for `routes_imported` 
        return ["routes_imported"]
```

```python
class MyEvent(EventData):
    @classmethod
    def metric_fields(cls) -> list[ComponentFields]:
        # will add a metric for `stats_total_count`
        return [
            ComponentFields(kind="stats", fields=["total_count"])
        ]
```

### metric_tags

This method is used to determine the tags that should be included in the metric data. It should return a list of strings or a list of ComponentTags instances.

It defaults to an empty list. You can override it if you want to include additional tags.

A `tag` represents a metric label that can be used for filtering or grouping. It is a string that represents the name of the tag.

Tags need to exists in one of the components sent with the event. If the tag does not exist, it will be ignored.

Tags are inserted with a `ctl_` prefix. If the component the tag is collected from has a `kind` property the prefix will be `ctl_<kind>_`.

```python
class MyEvent(EventData):
    @classmethod
    def metric_tags(cls) -> list[str]:
        # will add a metric label for `ctl_router_id` 
        return ["router_id"]

```

```python
class MyEvent(EventData):
    @classmethod
    def metric_tags(cls) -> list[ComponentTags]:
        # will add a metric label for `ctl_ix_name`
        return [
            ComponentTags(kind="ix", tags=["name"])
        ]
```

### get_metric_fields_and_tags

This method is used to determine the fields and tags that should be included in the metric data. It should return a `Metric` instance

```python
class Metric(pydantic.BaseModel):
    name: str
    fields: dict
    tags: dict = pydantic.Field(default_factory=dict)
```

It defaults to an empty `Metric` instance, that has `status` as a field and `ctl_object_id` and `ctl_org_id` as tags.

You can override it if you want to include additional fields or tags.

It is allowed to either return a single `Metric` instance, or a list of `Metric` instances.

You can also have it return None if no metric data should be generated for the event.

```python
class MyEvent(EventData):
    @classmethod
    def get_metric_fields_and_tags(cls) -> Metric | list[Metric] | None:
        return Metric(name="my_event", fields={"my_field": int}, tags={"my_tag": str})
```

## Specialized mixins

### MetricsSelectiveComponentMixin

Used for event data that stores a list of distinct components, where each component
describes a different part of the same event / metric.

All fields and tags will be collected into one metric, based on the `metric_fields` and `metric_tags` methods.

### MetricsMultiComponentMixin

Used for event data that stores a list of distinct components, where each component
is its own metric.

Each component will have its own metric, based on the `metric_fields` and `metric_tags` methods.