# Ports

[[_TOC_]]

## Port Up/Down

Allow IX operator to connect/disable device interfaces from IxCtl.

### IxCtl UI

Include a new button in Members list to enable/disable the port.

Handle a new click event from that button to send a request to the IxCtl API that toggles the port state.

### IxCtl API

Expose a new endpoint to toggle the port state.

```
PATCH /api/member/{org_tag}/{ix_tag}/{member_id}/
```

Use the `status` parameter to send the state value.

Use the `status` field in `member` to keep port state, values: `ok` or `admin_down`.

`ixctl_member` has a `port_id` pointing to `devicectl_port`.

Call DeviceCtl to update `port` state.

### DeviceCtl API

<!--
Define a new proxy URL `physical-port-enable` pointing to devicectl endpoint.
-->

Use an endpoint in devicectl to enable/disable the physical interfaces that belong to a port.

Traverse all `physical_ports` associated to that port.

```
PATCH /api/physical_port/{org_tag}/{physical_port_id}/
```

Use the `status` parameter into `physical_port` model to change interface state.

```d2
  style: {
    font: mono
    fill: transparent
  }

  ixCtl: {
    member: {
      shape: sql_table
      id: int {constraint: primary_key}
      ix_id: int {constraint: foreign_key}
      port_id: int {constraint: foreign_key}
      status: char
    }
    exchange: {
      shape: sql_table
      id: int {constraint: primary_key}
    }

    member.ix_id -> exchange.id
  }

  deviceCtl: {
    device: {
      shape: sql_table
      id: int {constraint: primary_key}
    }

    port: {
      shape: sql_table
      id: int {constraint: primary_key}
      virtual_port_id: int {constraint: foreign_key}
    }

    port_info: {
      shape: sql_table
      id: int {constraint: primary_key}
      status: char
    }

    virtual_port: {
      shape: sql_table
      id: int {constraint: primary_key}
      logical_port_id: int {constraint: foreign_key}
    }
    logical_port: {
      shape: sql_table
      width: 200
      id: int {constraint: primary_key}
    }
    physical_port: {
      shape: sql_table
      id: int {constraint: primary_key}
      device_id: int {constraint: foreign_key}
      logical_port_id: int {constraint: foreign_key}
      status: char
    }

    port.virtual_port_id -> virtual_port.id
    port.port_info_id -> port_info.id
    virtual_port.logical_port_id -> logical_port.id
    physical_port.logical_port_id -> logical_port.id
    physical_port.device_id -> device.id
  }

  ixCtl.member.port_id -> deviceCtl.port.id
```

### Device Management

`referee` has to be aware of interface state changes and configure the device.

```
[sergio@dev5 dev5]$ referee render --filter-device=sf_00 --debug --local-devel --print-config --git-readonly
```

```
2024-09-13T19:42:26.926063Z [debug    ] GET URL https://dev5.20c.com:8105/api/device/demo/1/ kwargs={}
2024-09-13T19:42:27.345066Z [debug    ] response 200                   response={"data": [{"name": "sf_00", "display_name": "sf_00", "type": "eos", "facility": 1, "facility_name": "Demo IXP Facility", "facility_slug": "demo-ixp-facility", "reference": null, "reference_source": null, "reference_is_sot": true, "reference_ux_url": null, "reference_api_url": null, "description": "Demo IXP Switch Fabric 00", "instance": 1, "management_ip_address_4": null, "management_ip_address_6": null, "operational_status": "ok", "tags": [], "meta": {"firmware_version": "4.32.0.1F-36950381.43201F"}, "grainy": "device.33.1", "id": 1, "status": "ok", "created": "2024-09-01T00:57:56.668221Z", "updated": "2024-09-09T17:17:27.367507Z"}], "errors": {}, "profiling": {"queries": 28}}

2024-09-13T19:48:15.414989Z [warning  ] get_interfaces not implemented for reference_source None
2024-09-13T19:48:15.415341Z [debug    ] GET URL https://dev5.20c.com:8103/api/sessions_summary/65534/device/1/ kwargs={}
2024-09-13T19:48:16.251595Z [debug    ] response 200                   response={"data": [], "errors": {}, "profiling": {"queries": 19}}
```

Build the Source of Truth for host getting the interfaces parameters in `create_template_vars()`.

Request device `physical_ports` parameters from deviceCtl using the existing `get_device_physical_ports()` from `fullctl_client`.

Example response.

```
{
  "device": 1,
  "device_name": "sf_00",
  "name": "Management0",
  "display_name": "Management0",
  "logical_port": 2,
  "logical_port_name": "Management0:lp",
  "description": "Demo IX sf_00 Physical Port to host",
  "metric": {
    "sf_00.interfaces_counters.Management0.rx_octets": 138458,
    "sf_00.interfaces_counters.Management0.tx_octets": 240546
  },
  "grainy": "physical_port.33.1",
  "id": 1,
  "status": "ok",
  "created": "2024-09-01T02:12:51.570715Z",
  "updated": "2024-09-01T02:12:51.623962Z"
}, {
  "device": 1,
  "device_name": "sf_00",
  "name": "Ethernet1",
  "display_name": "Ethernet1",
  "logical_port": 3,
  "logical_port_name": "Ethernet1:lp",
  "description": "Demo IX sf_pp Physical Port to rs_00",
  "metric": {
    "sf_00.interfaces_counters.Ethernet1.rx_octets": 720,
    "sf_00.interfaces_counters.Ethernet1.tx_octets": 888
  },
  "grainy": "physical_port.33.2",
  "id": 2,
  "status": "ok",
  "created": "2024-09-01T02:13:23.506801Z",
  "updated": "2024-09-01T02:13:23.551685Z"
}, {
  "device": 1,
  "device_name": "sf_00",
  "name": "Ethernet2",
  "display_name": "Ethernet2",
  "logical_port": 4,
  "logical_port_name": "Ethernet2:lp",
  "description": "Demo IX sf_00 Physical Port to as_10",
  "metric": {
    "sf_00.interfaces_counters.Ethernet2.rx_octets": 24840,
    "sf_00.interfaces_counters.Ethernet2.tx_octets": 1164
  },
  "grainy": "physical_port.33.3",
  "id": 3,
  "status": "ok",
  "created": "2024-09-01T02:13:46.992623Z",
  "updated": "2024-09-01T02:13:47.046571Z"
}, {
  "device": 1,
  "device_name": "sf_00",
  "name": "Ethernet3",
  "display_name": "Ethernet3",
  "logical_port": 5,
  "logical_port_name": "Ethernet3:lp",
  "description": "Demo IX sf_00 Physical Port to as_20",
  "metric": {
    "sf_00.interfaces_counters.Ethernet3.rx_octets": 25093,
    "sf_00.interfaces_counters.Ethernet3.tx_octets": 1164
  },
  "grainy": "physical_port.33.4",
  "id": 4,
  "status": "ok",
  "created": "2024-09-01T02:14:14.985220Z",
  "updated": "2024-09-01T02:14:15.027386Z"
}
```

Transform this response parameters to match the device template parameters.

```
{% if interface.enabled %}   no shutdown{% else %}   shutdown{% endif %}
```

#### Device

Disable

```
interface Ethernet1
  shutdown
```

Enable

```
interface Ethernet1
  no shutdown
```

Check

```
show interfaces status
```

Example

```
sf_00#configure terminal
sf_00(config)#interface Ethernet 3
sf_00(config-if-Et3)#shutdown
sf_00(config-if-Et3)#exit
sf_00(config)#exit
sf_00#show interfaces status
Port       Name     Status       Vlan     Duplex Speed  Type            Flags Encapsulation
Et1        To rs_00 connected    trunk    full   1G     EbraTestPhyPort
Et2        To as_10 connected    trunk    full   1G     EbraTestPhyPort
Et3        To as_20 disabled     trunk    full   1G     EbraTestPhyPort
Ma0                 connected    routed   a-full a-1G   10/100/1000
```

```
sf_00#configure terminal
sf_00(config)#interface Ethernet 3
sf_00(config-if-Et3)#no shutdown
sf_00(config-if-Et3)#exit
sf_00(config)#exit
sf_00#show interfaces status
Port       Name     Status       Vlan     Duplex Speed  Type            Flags Encapsulation
Et1        To rs_00 connected    trunk    full   1G     EbraTestPhyPort
Et2        To as_10 connected    trunk    full   1G     EbraTestPhyPort
Et3        To as_20 connected    trunk    full   1G     EbraTestPhyPort
Ma0                 connected    routed   a-full a-1G   10/100/1000
```
