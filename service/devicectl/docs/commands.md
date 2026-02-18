## devicectl_migrate_vlan_ids

Migrate legacy vlan_id values from virtual ports to vlan objects.

```sh
python manage.py devicectl_migrate_vlan_ids --commit
```

Expected output
```sh
Assigning VLAN 64 (Vlan 64) to VirtualPort(829) et-0/0/48
Assigning VLAN 64 (Vlan 64) to VirtualPort(863) GigabitEthernet0/0/0/14
Assigning VLAN 64 (Vlan 64) to VirtualPort(830) Wayfair LLC:lag0
Assigning VLAN 64 (Vlan 64) to VirtualPort(864) TenGigE0/1/0/1
Assigning VLAN 64 (Vlan 64) to VirtualPort(831) et-0/0/49
Assigning VLAN 64 (Vlan 64) to VirtualPort(865) TenGigE0/2/0/20
Assigning VLAN 64 (Vlan 64) to VirtualPort(832) TenGigE0/2/0/14
Assigning VLAN 64 (Vlan 64) to VirtualPort(833) TenGigE0/0/0/9
Assigning VLAN 64 (Vlan 64) to VirtualPort(834) Akamai:lag0
Assigning VLAN 64 (Vlan 64) to VirtualPort(835) TenGigE0/1/0/12
Assigning VLAN 64 (Vlan 64) to VirtualPort(836) TenGigE0/1/0/19
Assigning VLAN 64 (Vlan 64) to VirtualPort(837) Gi0/0/2
VLAN migration completed.
```

### Usage

```sh
usage: manage.py devicectl_migrate_vlan_ids [-h] [--commit] [--queue] [--timeout TIMEOUT]
                                            [--version] [-v {0,1,2,3}] [--settings SETTINGS]
                                            [--pythonpath PYTHONPATH] [--traceback]
                                            [--no-color] [--force-color] [--skip-checks]

Migrate vlan ids from virtual ports to vlan objects

options:
  -h, --help            show this help message and exit
  --commit              Commit changes
  --queue, -Q           Queue the execution of this command as a task
  --timeout TIMEOUT     Max execution time in queue (seconds)
  --version             Show program's version number and exit.
  -v {0,1,2,3}, --verbosity {0,1,2,3}
                        Verbosity level; 0=minimal output, 1=normal output, 2=verbose output,
                        3=very verbose output
  --settings SETTINGS   The Python path to a settings module, e.g. "myproject.settings.main".
                        If this isn't provided, the DJANGO_SETTINGS_MODULE environment
                        variable will be used.
  --pythonpath PYTHONPATH
                        A directory to add to the Python path, e.g.
                        "/home/djangoprojects/myproject".
  --traceback           Raise on CommandError exceptions.
  --no-color            Don't colorize the command output.
  --force-color         Force colorization of the command output.
  --skip-checks         Skip system checks.
```

## devicectl_netbox_sync

Netbox needs to be set up as a federated service for the organization in aaactl.

Relvant federated service settings:

- `DEVICE_ROLE` - list of device roles to sync (DEFAULT ["Edge Router"])
- `DEFAULT_PHY_TYPE` - default physical interface type to use for ports (DEFAULT "1000base-t")
- `INTERFACE_PHSYICAL` - list of partial interface names to match physical interfaces (DEFAULT [], EXAMPLE ["sfp"])
- `DEFAULT_MANUFACTURER` - default manufacturer to use for devices (DEFAULT "Unknown")

Synchronize data between DeviceCtl and Netbox for a specified organization. This command allows pulling data from Netbox into DeviceCtl and optionally pushing DeviceCtl data back to Netbox.

```sh
python manage.py devicectl_netbox_sync <org_slug> --commit [--push] [--purge]
```

Expected output
```sh
Pushing updates to netbox for example-org
Pulling netbox data for example-org
Pulled netbox data for example-org
```

### Usage

```sh
usage: manage.py devicectl_netbox_sync [-h] [--commit] [--push] [--purge] [--queue]
                                      [--timeout TIMEOUT] [--version] [-v {0,1,2,3}]
                                      [--settings SETTINGS] [--pythonpath PYTHONPATH]
                                      [--traceback] [--no-color] [--force-color]
                                      [--skip-checks]
                                      [org_slug]

Pull netbox data for specified organization

positional arguments:
  org_slug              Organization slug to sync with Netbox

options:
  -h, --help            show this help message and exit
  --commit             Commit changes
  --push               Push updates to netbox
  --purge              Purge devicectl data. This will delete devices and ports that have 
                      references to netbox that no longer exist.
  --queue, -Q          Queue the execution of this command as a task
  --timeout TIMEOUT    Max execution time in queue (seconds)
  --version           Show program's version number and exit.
  -v {0,1,2,3}, --verbosity {0,1,2,3}
                      Verbosity level; 0=minimal output, 1=normal output, 2=verbose output,
                      3=very verbose output
  --settings SETTINGS  The Python path to a settings module, e.g. "myproject.settings.main".
                      If this isn't provided, the DJANGO_SETTINGS_MODULE environment
                      variable will be used.
  --pythonpath PYTHONPATH
                      A directory to add to the Python path, e.g.
                      "/home/djangoprojects/myproject".
  --traceback         Raise on CommandError exceptions.
  --no-color          Don't colorize the command output.
  --force-color       Force colorization of the command output.
  --skip-checks       Skip system checks.

### Examples

1. Pull data from Netbox for a specific organization:
```sh
python manage.py devicectl_netbox_sync acme-networks --commit
```

2. Pull from Netbox and remove stale references:
```sh
python manage.py devicectl_netbox_sync acme-networks --commit --purge
```

3. Bi-directional sync (push to and pull from Netbox):
```sh
python manage.py devicectl_netbox_sync acme-networks --commit --push
```

4. Queue the sync operation as a background task with a timeout:
```sh
python manage.py devicectl_netbox_sync acme-networks --commit --push --queue --timeout 3600
```

5. Dry run to see what would be synchronized:
```sh
python manage.py devicectl_netbox_sync acme-networks
```

### Notes

- The `--push` flag requires `--commit` to be set
- When `--purge` is enabled, the command will delete DeviceCtl devices and ports that reference Netbox objects that no longer exist
- Organization slug must correspond to an existing organization in the system
- Command will synchronize device and port data between DeviceCtl and Netbox