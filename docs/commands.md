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