# Metrics

Visualize port metrics.

[[_TOC_]]

## Frontend

### Summary Page

Add column into the table.

```
/ssh:dev5.ch2.mgmt.20c.com:/home/sergio/fullctl/dev-env/peerctl/src/django_peerctl/templates/peerctl/v2/tool/peering-summary-sessions/main.html
```

Add an action to show metrics on click a port.

```html
data-action="show_port_metrics"
```

Data

```html
data-api-base="/api/sessions_summary/65534/"
```

### Details Page

Add new page

```
/ssh:dev5.ch2.mgmt.20c.com:/home/sergio/fullctl/dev-env/peerctl/src/django_peerctl/templates/peerctl/v2/tool/peer-session/main.html
```

## Backend

Add metrics

https://dev5.20c.com:8103/api/sessions_summary/65534/device/9/

### peerCtl
#### View

```
/ssh:dev5.ch2.mgmt.20c.com:/home/sergio/fullctl/dev-env/peerctl/src/django_peerctl/rest/views/peerctl.py
```

Nothing to do here.

#### Serializer

```
/ssh:dev5.ch2.mgmt.20c.com:/home/sergio/fullctl/dev-env/peerctl/src/django_peerctl/rest/serializers/peerctl.py
```

Add metric to `PeerSession`

```python
class PeerSession(ModelSerializer):
```

#### Model

```
/ssh:dev5.ch2.mgmt.20c.com:/home/sergio/fullctl/dev-env/peerctl/src/django_peerctl/models/peerctl.py
```

Join `physical_ports` data.

```python
class PeerSession(PolicyHolderMixin, meta.DataMixin, Base):

    port = ReferencedObjectField(bridge=Port, null=True, blank=True)

    def load_references(cls, sessions):
        Port.load_references(port_infos + sessions, join="device")
```

### deviceCtl

https://dev5.20c.com:8105/api/service-bridge/data/port/?ids=0%2C37&join=device

#### Serializer

```
/ssh:dev5.ch2.mgmt.20c.com:/home/sergio/fullctl/dev-env/devicectl/src/django_devicectl/rest/serializers/service_bridge.py
```

Add `metric` into `PhysicalPort` serializer.

```python
class PhysicalPort(ModelSerializer):
    metric = serializers.SerializerMethodField()
```
