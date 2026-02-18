# Settings

- `NAUTOBOT_URL`: url of the nautobot instance
- `NAUTOBOT_TOKEN`: api token to use for authentication
  - The token can be created through nautobot admin interface
  - The token needs full permissions to the following models:
    - `dcim | device`
    - `dcim | device type`
    - `dcim | site`
    - `extras | custom field`

- `SERVICE_BRIDGE_REF_DEVICE`: set to `fullctl.service_bridge.nautobot.Device` to tell devicectl that nautobot is the source of truth for devices.

## Import service-bridge actions

```
Ctl/dev/run.sh loaddata fixtures/nautobot.actions.json
```

or by calling `manage` in side the container

```
manage loaddata ../fixtures/nautobot.actions.json
```


## Make sure a `fullctl_poll_tasks` process is running in the devicectl container

```
manage fullctl_poll_tasks --wrokers 4
```

## Sync changes from nautobot to devicectl

### 1. Run `devicectl_nautobot_pull` job

```sh
python manage.py devicectl_nautobot_pull {org.slug} --commit
```

### 2. Set up nautobot fullctl integration

Install the [nautobot_fullctl](https://github.com/fullctl/nautobot_fullctl) addon into nautobot.

Aftewards device changes will be synced directly to devicectl from nautobot using the service bridge.

Note: devices need to be added to facilities in devicectl before they show up

## Sync changes from devicectl to nautobot

- Facilities
- Device location
