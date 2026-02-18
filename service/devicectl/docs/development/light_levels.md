# DeviceCtl Light Levels Implementation Proposal

Store light level metrics.

[[_TOC_]]

## Collect Data Workflow

Call CLI command to get data from device and send it to deviceCtl.

```bash
referee sitrep-light-levels --filter-device=ceos00
```

referee gets data from device.

```
2024-07-26T17:53:49.872009Z [debug    ] Get light levels results={'arista': {'optics': {}}}
```

referee posts data to deviceCtl.

```
2024-07-26T17:53:49.872554Z [debug    ] POST URL https://dev5.20c.com:8105/api/device/demo/7/metric/ kwargs={'data': {'arista': {'opti
```

When you send a POST request to create a new metric, the JSON payload can look like this:

```json
{
	"data": {
	    "arista": {
	        "optics": {
	            "et1": {
	                "physical_channels": {
	                    "channel": [
	                        {
	                            "index": 0,
	                            "state": {
	                                "input_power": {
	                                    "instant": 0.0,
	                                    "avg": 0.0,
	                                    "min": 0.0,
	                                    "max": 0.0,
	                                },
	                                "output_power": {
	                                    "instant": 0.0,
	                                    "avg": 0.0,
	                                    "min": 0.0,
	                                    "max": 0.0,
	                                },
	                                "laser_bias_current": {
	                                    "instant": 0.0,
	                                    "avg": 0.0,
	                                    "min": 0.0,
	                                    "max": 0.0,
	                                },
	                            },
	                        }
	                    ]
	                }
	            }
	        }
	    }
	}
}
```

## Model To Store Last Result Into Database

Generic metric model.

Handle JSON payloads without being aware of the specific structure of the metrics.

```
/ssh:dev5.ch2.mgmt.20c.com:/home/sergio/fullctl/dev-env/devicectl/src/django_devicectl/models/devicectl.py
```

```python
class Metric():
    data = models.JSONField()
    timestamp = models.DateTimeField()
```

```shell
docker exec -it dev-custom-devicectl_web-1 python main/manage.py makemigrations
docker exec -it dev-custom-devicectl_web-1 python main/manage.py migrate
```

## Serializer For The Model

```
/ssh:dev5.ch2.mgmt.20c.com:/home/sergio/fullctl/dev-env/devicectl/src/django_devicectl/rest/serializers/devicectl.py
```

```python
class MetricSerializer():
    class Meta:
        model = models.Metric
        fields = ['data', 'timestamp']
```

## View To Handle REST Post Method

Used by referee to send data.

```
/ssh:dev5.ch2.mgmt.20c.com:/home/sergio/fullctl/dev-env/devicectl/src/django_devicectl/rest/views/devicectl.py
```

```python
@route
class Device(CachedObjectMixin, viewsets.GenericViewSet):
    ...
    @action(detail=True, methods=["post"])
    @grainy_endpoint(namespace="device.{request.org.permission_id}.{device_id}")
    @load_object("device", models.Device, instance="instance", id="device_id")
    def metric(self, request, org, instance, device_id, device, *args, **kwargs):
        """
        Create a new Metric instance from a JSON payload in a Device.

        The JSON payload should include 'data' keys. The timestamp
        is automatically set to the current time.
        """
        serializer = Serializers.metric(data=request.data)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
```

## View To Handle REST Get Method

Used by ixCtl to visualize data.

```
/ssh:dev5.ch2.mgmt.20c.com:/home/sergio/fullctl/dev-env/devicectl/src/django_devicectl/rest/views/devicectl.py
```

```python
@route
class Metric(viewsets.ModelViewSet):
    """A viewset for viewing Metric instances."""

    serializer_class = Serializers.metric
    queryset = models.Metric.objects.all()

    @action(detail=False, methods=["get"], url_path="ix/(?P<ix_id>[^/.]+)")
    @grainy_endpoint(namespace="device.{request.org.permission_id}")
    def ix(self, request, org, instance, ix_id, *args, **kwargs):
        """Returns metric data points."""
        result = self.serializer_class(self.queryset, many=True).data
        return Response(result)
```

## For Further Discussion
### Remove Previous Stored Metric

PostgreSQL should only store the last result.

### Store Result Into Time Series Database

Add call to store into TSDB.
