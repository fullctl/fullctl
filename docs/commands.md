## ixctl_fix_port_config

Will cycle through all the members of an exchange and fix the port configuration for each member, based
on what is the source of truth in deviceCtl.

The following fields will be updated:

- port_quantity
- port_size
- lag

### Examples

```shell
# Fix the port configuration for all members of a specific exchange
python manage.py ixctl_fix_port_config --org demo --ix chix --commit

# Fix the port configuration for all members of all exchanges in an organization
python manage.py ixctl_fix_port_config --org demo --commit
```

### Expected output

```shell
Checking 9 members for chix
AS63311 - 10.10.10.1 - None (3364) port_quantity: 2 -> 1
AS63311 - 10.10.10.1 - None (3364) lag: True -> False
AS63311 - 10.10.10.1 - None (3364) port_size: 100 -> 10
Saving 1 members for chix
```
### Usage

```shell
usage: manage.py ixctl_fix_port_config [-h] [--commit] [--queue] [--timeout TIMEOUT] [--org ORG] [--ix IX] [--speed SPEED]
                                       [--version] [-v {0,1,2,3}] [--settings SETTINGS] [--pythonpath PYTHONPATH]
                                       [--traceback] [--no-color] [--force-color] [--skip-checks]

Fixes the port configuration intent values of existing internet exchange members, according to the source of truth that
exists in devicectl

options:
  -h, --help            show this help message and exit
  --commit              Commit changes
  --queue, -Q           Queue the execution of this command as a task
  --timeout TIMEOUT     Max execution time in queue (seconds)
  --org ORG             Organization slug - if specified, will fix all exchanges in the organization
  --ix IX               Internet Exchange slug - if specified, will fix only this exchange
  --speed SPEED         Fallback speed in Gb/s for ports that do not have a speed set in devicectl
  --version             Show program's version number and exit.
  -v {0,1,2,3}, --verbosity {0,1,2,3}
                        Verbosity level; 0=minimal output, 1=normal output, 2=verbose output, 3=very verbose output
  --settings SETTINGS   The Python path to a settings module, e.g. "myproject.settings.main". If this isn't provided, the
                        DJANGO_SETTINGS_MODULE environment variable will be used.
  --pythonpath PYTHONPATH
                        A directory to add to the Python path, e.g. "/home/djangoprojects/myproject".
  --traceback           Raise on CommandError exceptions.
  --no-color            Don't colorize the command output.
  --force-color         Force colorization of the command output.
  --skip-checks         Skip system checks.
  ```