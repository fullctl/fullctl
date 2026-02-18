## Settings

### Nautobot integration

Currently it is only possible to configure a global url and token for nautobot usage. Per organization configuration is planned going forward.

- `NAUTOBOT_URL` - should point to your nautobot instance without trailing `/`
- `NAITOBOT_TOKEN` - api token that will be used

### Graphing

- `GRAPHS_PATH` - path to store generated RRD graphs
- `GRAPHS_URL` - url to access generated RRD graphs
- `GRAPHS_RRD_ENABLED` - enable or disable RRD graphing (default: `True`)

### Physical Port Stats

- `PHYSICAL_PORT_STATS_BGP_STALE_AFTER` - after how long are bgp stats considered stale, in seconds (default: `600`)