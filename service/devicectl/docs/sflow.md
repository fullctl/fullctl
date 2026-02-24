# Index

- [REST Api](#rest-api)
  - [IX traffic: total](#ix-traffic-total)
  - [Port traffic: total](#port-traffic-total)
  - [Port Traffic: for ASN to all other ASNs](#port-traffic-for-asn-to-all-other-asns)
  - [Port traffic: between two ASNs](#port-traffic-between-two-asns)
  - [Port traffic: ASN table](#port-traffic-asn-table)
- [Service bridge](#service-bridge)
  - [Port traffic: total](#service-bridge-port-traffic-total)
  - [Port traffic: between two ASNs](#service-bridge-port-traffic-between-two-asns)
  - [Port traffic: ASN table](#service-bridge-port-traffic-asn-table)
- [Metric python client](#metrics-python-client)
  - [Create sflow data](#create-sflow-data)
  - [Query examples](#query-examples)
    - [Query graph metrics (Bps in/out, max Bps in/out for a port)](#query-graph-metrics-bps-inout-max-bps-inout-for-a-port)
    - [Query graph metrics (Bps in/out, max Bps in/out for an IX)](#query-graph-metrics-bps-inout-max-bps-inout-for-an-ix)

# REST API
### IX traffic: total

```py
import requests

org_slug = "demo"
ix_id = 1
host = "https://device.fullctl.com"
# step size in seconds
step = 3600
# start offset (2 hours ago) - can also be a unix timestamp or a iso8601 date
start = "-2h"
api_key = "your-api-key"

url = f"{host}/api/metric/sflow/{org_slug}/graph/ix/{ix_id}/?step={step}&start={start}"

response = requests.get(url, headers={"Authorization": f"Bearer {api_key}"})
```

We are requesting the total traffic for an IX for the last 2 hours with a step size of 1 hour, so we expect 2 datapoints in each metric.

```json
{
  "data": [
    {
      "status": "success",
      "error": null,
      "errorType": null,
      "data": {
        "resultType": "matrix",
        "result": [
          {
            "metric": {
              "metric": "bps_in"
            },
            "value": null,
            "values": [
              [1724313706.006, 680514646.471111],
              [1724317306.006, 597991041.706667]
            ]
          },
          {
            "metric": {
              "metric": "bps_in_max"
            },
            "value": null,
            "values": [
              [1724313706.006, 1098797765.97333],
              [1724317306.006, 1133948654.93333]
            ]
          },
          {
            "metric": {
              "metric": "bps_out"
            },
            "value": null,
            "values": [
              [1724313706.006, 680514646.471111],
              [1724317306.006, 597991041.706667]
            ]
          },
          {
            "metric": {
              "metric": "bps_out_max"
            },
            "value": null,
            "values": [
              [1724313706.006, 1098797765.97333],
              [1724317306.006, 1133948654.93333]
            ]
          }
        ]
      },
      "stats": {
        "seriesFetched": "8",
        "executionTimeMsec": 18
      }
    }
  ],
  "errors": {

  },
  "profiling": {
    "queries": 20
  }
}
```

### Port traffic: total

```py
import requests

org_slug = "demo"
port_id = 1
host = "https://device.fullctl.com"
# step size in seconds
step = 3600
# start offset (2 hours ago) - can also be a unix timestamp or a iso8601 date
start = "-2h"
api_key = "your-api-key"

url = f"{host}/api/metric/sflow/{org_slug}/graph/port/{port_id}/?step={step}&start={start}"

response = requests.get(url, headers={"Authorization": f"Bearer {api_key}"})
```

We are requesting the total traffic for a port for the last 2 hours with a step size of 1 hour, so we expect 2 datapoints in each metric.

```json
{
  "data": [
    {
      "status": "success",
      "error": null,
      "errorType": null,
      "data": {
        "resultType": "matrix",
        "result": [
          {
            "metric": {
              "metric": "bps_in"
            },
            "value": null,
            "values": [
              [1724313856.047, 663519796.337778],
              [1724317456.047, 777324116.195556]
            ]
          },
          {
            "metric": {
              "metric": "bps_in_max"
            },
            "value": null,
            "values": [
              [1724313856.047, 61380580.6933333],
              [1724317456.047, 1133948654.93333]
            ]
          },
          {
            "metric": {
              "metric": "bps_out"
            },
            "value": null,
            "values": [
              [1724313856.047, 697509496.604445],
              [1724317456.047, 418657967.217778]
            ]
          },
          {
            "metric": {
              "metric": "bps_out_max"
            },
            "value": null,
            "values": [
              [1724313856.047, 1098797765.97333],
              [1724317456.047, 81514769.0666667]
            ]
          }
        ]
      },
      "stats": {
        "seriesFetched": "4",
        "executionTimeMsec": 2
      }
    }
  ],
  "errors": {

  },
  "profiling": {
    "queries": 20
  }
}
```

### Port Traffic for ASN to all other ASNs

```py
import requests

org_slug = "demo"
port_id = 1
asn = 1
host = "https://device.fullctl.com"
# step size in seconds
step = 3600
# start offset (2 hours ago) - can also be a unix timestamp or a iso8601 date
start = "-2h"
api_key = "your-api-key"

url = f"{host}/api/metric/sflow/{org_slug}/graph/port/{port_id}/asn/{asn}/?step={step}&start={start}"

response = requests.get(url, headers={"Authorization": f"Bearer {api_key}"})
```

We are requesting the total traffic for a port for the last 2 hours with a step size of 1 hour, so we expect 2 datapoints in each metric.

Each metric will also specify the opposite ASN in either `ctl_asn_dst` or `ctl_asn_src` depending on direction.

```json
{
  "data": [
    {
      "status": "success",
      "error": null,
      "errorType": null,
      "data": {
        "resultType": "matrix",
        "result": [
          {
            "metric": {
              "ctl_asn_dst": "38880",
              "metric": "bps_out"
            },
            "value": null,
            "values": [
              [
                1724313909.58,
                793098904.4622222
              ],
              [
                1724317509.58,
                413721522.6311111
              ]
            ]
          },
          {
            "metric": {
              "ctl_asn_src": "38880",
              "metric": "bps_in"
            },
            "value": null,
            "values": [
              [
                1724313909.58,
                517902681.8844444
              ],
              [
                1724317509.58,
                779018531.2711111
              ]
            ]
          },
          {
            "metric": {
              "ctl_asn_src": "38880",
              "metric": "bps_in_max"
            },
            "value": null,
            "values": [
              [
                1724313909.58,
                56343702.18666667
              ],
              [
                1724317509.58,
                76676683.09333333
              ]
            ]
          },
          {
            "metric": {
              "ctl_asn_dst": "38880",
              "metric": "bps_out_max"
            },
            "value": null,
            "values": [
              [
                1724313909.58,
                1189239848.96
              ],
              [
                1724317509.58,
                1130002513.92
              ]
            ]
          }
        ]
      },
      "stats": {
        "seriesFetched": "4",
        "executionTimeMsec": 3
      }
    }
  ],
  "errors": {},
  "profiling": {
    "queries": 11
  }
}
```

### Port traffic between two ASNs

```py
import requests

org_slug = "demo"
port_id = 1
asn_a = 63311
asn_b = 63312
host = "https://device.fullctl.com"
# step size in seconds
step = 3600
# start offset (2 hours ago) - can also be a unix timestamp or a iso8601 date
start = "-2h"
api_key = "your-api-key"

url = f"{host}/api/metric/sflow/{org_slug}/graph/port/{port_id}/asn/{asn_a}/{asn_b}/?step={step}&start={start}"

requests.get(url, headers={"Authorization": f"Bearer {api_key}"})
```

We are requesting the total traffic for a port for the last 2 hours with a step size of 1 hour, so we expect 2 datapoints in each metric.

```json
{
  "data": [
    {
      "status": "success",
      "error": null,
      "errorType": null,
      "data": {
        "resultType": "matrix",
        "result": [
          {
            "metric": {
              "metric": "bps_out"
            },
            "value": null,
            "values": [
              [1724314061.167, 793098904.462222],
              [1724317661.167, 413721522.631111]
            ]
          },
          {
            "metric": {
              "metric": "bps_in"
            },
            "value": null,
            "values": [
              [1724314061.167, 517902681.884444],
              [1724317661.167, 779018531.271111]
            ]
          },
          {
            "metric": {
              "metric": "bps_in_max"
            },
            "value": null,
            "values": [
              [1724314061.167, 56343702.1866667],
              [1724317661.167, 76676683.0933333]
            ]
          },
          {
            "metric": {
              "metric": "bps_out_max"
            },
            "value": null,
            "values": [
              [1724314061.167, 1189239848.96],
              [1724317661.167, 1130002513.92]
            ]
          }
        ]
      },
      "stats": {
        "seriesFetched": "4",
        "executionTimeMsec": 9
      }
    }
  ],
  "errors": {

  },
  "profiling": {
    "queries": 20
  }
}
```

### Port traffic ASN table

```py
import requests

org_slug = "demo"
port_id = 1
host = "https://device.fullctl.com"
# step size in seconds
step = 3600
# start offset (2 hours ago) - can also be a unix timestamp or a iso8601 date
start = "-2h"
api_key = "your-api-key"

url = f"{host}/api/metric/sflow/{org_slug}/graph/port/{port_id}/asn-table/"

response = requests.get(url, headers={"Authorization": f"Bearer {api_key}"})
```

```json
{
  "data": [
    {
      "asn": 38880,
      "name": "Micron21 Datacentre and Colocation",
      "bps_in_current": 565141741,
      "bps_in_average": 654494743,
      "bps_in_max": 1142659700,
      "bps_out_current": 588282247,
      "bps_out_average": 552806464,
      "bps_out_max": 59900996
    }
  ]
}
```

# Service bridge

## Service Bridge: Port traffic: total

```py
import fullctl.service_bridge.devicectl as devicectl

port_id = 1157
start = "-2h"
duration = None
step = 3600
traffic_source = "vm_sflow"

traffic = devicectl.VirtualPort().traffic(
  port_id, start, duration, step, traffic_source
)
```

```json
[
  {
    "status": "success",
    "error": null,
    "errorType": null,
    "data": {
      "resultType": "matrix",
      "result": [
        {
          "metric": {
            "metric": "bps_in"
          },
          "value": null,
          "values": [
            [
              1724325831.936,
              828956763.0222223
            ],
            [
              1724329431.936,
              510741599.5733333
            ]
          ]
        },
        {
          "metric": {
            "metric": "bps_in_max"
          },
          "value": null,
          "values": [
            [
              1724325831.936,
              1124706331.3066666
            ],
            [
              1724329431.936,
              37567638.18666667
            ]
          ]
        },
        {
          "metric": {
            "metric": "bps_out"
          },
          "value": null,
          "values": [
            [
              1724325831.936,
              425566116.9777778
            ],
            [
              1724329431.936,
              678370745.4577777
            ]
          ]
        },
        {
          "metric": {
            "metric": "bps_out_max"
          },
          "value": null,
          "values": [
            [
              1724325831.936,
              83121930.24
            ],
            [
              1724329431.936,
              1061038762.6666666
            ]
          ]
        }
      ]
    },
    "stats": {
      "seriesFetched": "4",
      "executionTimeMsec": 54
    }
  }
]
```

## Service Bridge: Port traffic between two ASNs

```py
import fullctl.service_bridge.devicectl as devicectl

port_id = 1157
asn_a = 9342
asn_b = 38880
start = "-2h"
duration = None
step = 3600

traffic = devicectl.VirtualPort().traffic_asn_pair(
  port_id, asn_a, asn_b, start, duration, step
)
```

```json
[
  {
    "status": "success",
    "error": null,
    "errorType": null,
    "data": {
      "resultType": "matrix",
      "result": [
        {
          "metric": {
            "metric": "bps_out"
          },
          "value": null,
          "values": [
            [
              1724326091.075,
              514781948.58666664
            ],
            [
              1724329691.075,
              589435881.2444445
            ]
          ]
        },
        {
          "metric": {
            "metric": "bps_in"
          },
          "value": null,
          "values": [
            [
              1724326091.075,
              740989119.1466666
            ],
            [
              1724329691.075,
              583487396.9777777
            ]
          ]
        },
        {
          "metric": {
            "metric": "bps_in_max"
          },
          "value": null,
          "values": [
            [
              1724326091.075,
              48261147.306666665
            ],
            [
              1724329691.075,
              921210716.16
            ]
          ]
        },
        {
          "metric": {
            "metric": "bps_out_max"
          },
          "value": null,
          "values": [
            [
              1724326091.075,
              1143938307.4133334
            ],
            [
              1724329691.075,
              76719936.85333334
            ]
          ]
        }
      ]
    },
    "stats": {
      "seriesFetched": "4",
      "executionTimeMsec": 57
    }
  }
]
```

## Service Bridge: Port traffic ASN table

```py
import fullctl.service_bridge.devicectl as devicectl

port_id = 1157
start = "-2h"
duration = None
step = 3600
traffic_source = "vm_sflow"

traffic = devicectl.VirtualPort().traffic_asn_table(
  port_id, start, duration, step
)
```

```json
[
  {
    "asn": 38880,
    "name": "Micron21 Datacentre and Colocation",
    "bps_in_current": 565141741,
    "bps_in_average": 654494743,
    "bps_in_max": 1142659700,
    "bps_out_current": 588282247,
    "bps_out_average": 552806464,
    "bps_out_max": 59900996
  }
]
```

# Metrics python client

## Create sflow data

```py
from django.conf import settings
from fullctl.metrics import Metrics
import time
from typing import Dict, Any

# Initialize the Metrics client
metrics = Metrics(settings.TIMESERIES_DB_URL)

# Device and organization details
device_id = 1001
org_id = 5001
interfaces = ["interface-0", "interface-1", "interface-2", "interface-3"]
service = "devicectl"

def process_sflow_data(metrics: Metrics, sflow_data: Dict[str, Any]):
    """
    Process a single sFlow data point and write it to VictoriaMetrics.

    Arguments:

    - metrics: Metrics instance for writing to VictoriaMetrics
    - sflow_data: A dictionary containing sFlow data

    {
      # labels
      "org": "wqhbct1kumm",
      "org_id": "2",
      "ix_id": "28",
      "asn_src": "9342",
      "asn_dst": "38880",
      "port_id_src": "1157",
      "port_id_dst": "1158",
      "device_id_src": "459",
      "device_id_dst": "460",
      "mac_src": "00:1a:2b:3c:4
      "mac_dst": "f8:e7:d6:c5:b4:a3"
      "timestamp": 1631532972,

      # sFlow data
      "bytes": 427862,
      "packets": 544,
    }


    """
    timestamp = int(sflow_data["timestamp"])

    metrics.write(
        measurement="sflow",
        tags={
            "ctl_service": service,
            "ctl_org": sflow_data["org"],
            "ctl_org_id": sflow_data["org_id"],
            "ctl_ix_id": sflow_data["ix_id"],
            "ctl_asn_src": sflow_data["asn_src"],
            "ctl_asn_dst": sflow_data["asn_dst"],
            "ctl_port_id_src": sflow_data["port_id_src"],
            "ctl_port_id_dst": sflow_data["port_id_dst"],
            "ctl_device_id_src": sflow_data["device_id_src"],
            "ctl_device_id_dst": sflow_data["device_id_dst"],
            "ctl_mac_src": sflow_data["mac_src"],
            "ctl_mac_dst": sflow_data["mac_dst"],
        },
        fields={
            "bytes": sflow_data["bytes"],
            "packets": sflow_data["packets"],
        },
        timestamp=timestamp
    )
```

## Query examples

### Query graph metrics (Bps in/out, max Bps in/out for a port)

```py
org_id = 2
ix_id = 28
port_id = 1157

# step size
step = "1h"

# lower step for the max() aggregation since rate_over_sum
# returns a single value for the step
#
# if steps are identical for avg() and max() their values
# will be the same
step_max = "5m"

# start offset (1 hour ago)
start = "-24h"

# we filter by org_id and port_id_src and port_id_dst (note the `ctl_` prefix)
#
# its important to provide both to ensure we are staying
# within the scope of the organization and IX
tags_in = f"ctl_org_id=\"{org_id}\", ctl_port_id_dst=\"{port_id}\""
tags_out = f"ctl_org_id=\"{org_id}\", ctl_port_id_src=\"{port_id}\""

# Base query that we can then format
TRAFFIC_GRAPH_QUERY_BASE = """
avg by (metric) (
    label_replace(
        rate_over_sum(sflow_bytes{{{tags_in}}}[{step}]),
        "metric", "bps_in", "", ""
    ) * 8
) or
max by (metric) (
    label_replace(
        rate_over_sum(sflow_bytes{{{tags_in}}}[{step_max}]),
        "metric", "bps_in_max", "", ""
    ) * 8 @ {step}
) or
avg by (metric) (
    label_replace(
        rate_over_sum(sflow_bytes{{{tags_out}}}[{step}]),
        "metric", "bps_out", "", ""
    ) * 8
) or
max by (metric) (
    label_replace(
        rate_over_sum(sflow_bytes{{{tags_out}}}[{step_max}]),
        "metric", "bps_out_max", "", ""
    ) * 8 @ {step}
)
"""

query = TRAFFIC_GRAPH_QUERY_BASE.fomrat(
    tags_in=tags_in,
    tags_out=tags_out,
    step=step,
    step_max=step_max
)

metrics.query_range(query, start=start, step=step)
```

```json
{
  "data": [
    {
      "status": "success",
      "error": null,
      "errorType": null,
      "data": {
        "resultType": "matrix",
        "result": [
          {
            "metric": {
              "metric": "bps_in"
            },
            "value": null,
            "values": [
              [1724190444.917, 40761444.1244445],
              [1724194044.917, 58590349.0844444],
              // ...
            ]
          },
          {
            "metric": {
              "metric": "bps_in_max"
            },
            "value": null,
            "values": [
              [1724194044.917, 88054388.0533333],
              [1724197644.917, 32647850.6666667],
              // ...
            ]
          },
          {
            "metric": {
              "metric": "bps_out"
            },
            "value": null,
            "values": [
              [1724190444.917, 38838126.3644444],
              [1724194044.917, 43050034.0622222],
              // ...
            ]
          },
          {
            "metric": {
              "metric": "bps_out_max"
            },
            "value": null,
            "values": [
              [1724194044.917, 52933864.1066667],
              [1724197644.917, 54139508.0533333],
              // ...
            ]
          }
        ]
      },
      "stats": {
        "seriesFetched": "4",
        "executionTimeMsec": 40
      }
    }
  ],
  "errors": {

  },
  "profiling": {
    "queries": 20
  }
}
```

### Query graph metrics (Bps in/out, max Bps in/out for an IX)

```py
org_id = 2
ix_id = 28

# step size
step = "1h"

# lower step for the max() aggregation since rate_over_sum
# returns a single value for the step
#
# if steps are identical for avg() and max() their values
# will be the same
step_max = "5m"

# start offset (1 hour ago)
start = "-24h"

# we filter by org_id and ix_id (note the `ctl_` prefix)
#
# its important to provide both to ensure we are staying
# within the scope of the organization and IX
tags_in = f"ctl_org_id=\"{org_id}\", ctl_ix_id=\"{ix_id}\", ctl_port_id_dst!=\"\""
tags_out = f"ctl_org_id=\"{org_id}\", ctl_ix_id=\"{ix_id}\", ctl_port_id_src!=\"\""

# Base query that we can then format
TRAFFIC_GRAPH_QUERY_BASE = """
avg by (metric) (
    label_replace(
        rate_over_sum(sflow_bytes{{{tags_in}}}[{step}]),
        "metric", "bps_in", "", ""
    ) * 8
) or
max by (metric) (
    label_replace(
        rate_over_sum(sflow_bytes{{{tags_in}}}[{step_max}]),
        "metric", "bps_in_max", "", ""
    ) * 8 @ {step}
) or
avg by (metric) (
    label_replace(
        rate_over_sum(sflow_bytes{{{tags_out}}}[{step}]),
        "metric", "bps_out", "", ""
    ) * 8
) or
max by (metric) (
    label_replace(
        rate_over_sum(sflow_bytes{{{tags_out}}}[{step_max}]),
        "metric", "bps_out_max", "", ""
    ) * 8 @ {step}
)
"""

query = TRAFFIC_GRAPH_QUERY_BASE.fomrat(
    tags_in=tags_in,
    tags_out=tags_out,
    step=step,
    step_max=step_max
)

metrics.query_range(query, start=start, step=step)
```

```json
{
  "data": [
    {
      "status": "success",
      "error": null,
      "errorType": null,
      "data": {
        "resultType": "matrix",
        "result": [
          {
            "metric": {
              "metric": "bps_out"
            },
            "value": null,
            "values": [
              [1724190274.126, 40874930.6311111],
              [1724193874.126, 38638878.72],
              // ...
            ]
          },
          {
            "metric": {
              "metric": "bps_in"
            },
            "value": null,
            "values": [
              [1724190274.126, 46203444.3377778],
              [1724193874.126, 51252483.4133333],
              // ...
            ]
          },
          {
            "metric": {
              "metric": "bps_in_max"
            },
            "value": null,
            "values": [
              [1724193874.126, 83122367.1466667],
              [1724197474.126, 33460278.6133333],
              [1724201074.126, 51380442.4533333],
              // ...
            ]
          },
          {
            "metric": {
              "metric": "bps_out_max"
            },
            "value": null,
            "values": [
              [1724193874.126, 36787978.24],
              [1724197474.126, 48718807.04],
              // ...
            ]
          }
        ]
      },
      "stats": {
        "seriesFetched": "4",
        "executionTimeMsec": 23
      }
    }
  ],
  "errors": {

  },
  "profiling": {
    "queries": 20
  }
}
```