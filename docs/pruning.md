## Prune old events

You can use the `auditctl_prune` django management command to remove old events from the database. This command will remove all events older than the specified number of days.

```bash
python manage.py auditctl_prune --max-age 30 --commit
```

In the example above, all events older than 30 days will be removed from the database. The `--commit` flag is required to actually remove the events. If you omit the `--commit` flag, the command will only show you the number of events that would be removed.

Removed entries are backed up to a JSON file in the current directory. You can specify a different output path using the `-o` flag.

```bash
python manage.py auditctl_prune --max-age 30 --commit -o /path/to/output.json
```

If you want to just see the number of events that would be removed without actually removing them, you can omit the `--commit` flag.

```bash
python manage.py auditctl_prune --max-age 30
```

### Settings
#### EVENT_MAX_AGE

If no max-age is specified, the command will use the `EVENT_MAX_AGE` setting from the `auditctl` settings file. (Settable via environment variable `EVENT_MAX_AGE`)

```bash
export EVENT_MAX_AGE=30
python manage.py auditctl_prune --commit
```

### Usage

```bash
usage: manage.py auditctl_prune [-h] [--commit] [--queue] [--timeout TIMEOUT] [-a MAX_AGE]
                                [-o OUTPUT_PATH] [--version] [-v {0,1,2,3}] [--settings SETTINGS]
                                [--pythonpath PYTHONPATH] [--traceback] [--no-color] [--force-color]
                                [--skip-checks]

Prune old audit log event entries

options:
  -h, --help            show this help message and exit
  --commit              Commit changes
  --queue, -Q           Queue the execution of this command as a task
  --timeout TIMEOUT     Max execution time in queue (seconds)
  -a MAX_AGE, --max-age MAX_AGE
                        Maximum age of entries to retain in days. If not specified `EVENT_MAX_AGE` will
                        be used.
  -o OUTPUT_PATH, --output-path OUTPUT_PATH
                        Path where the dumped JSON will be stored. If omitted, the current directory
                        will be used.
  --version             Show program's version number and exit.
  -v {0,1,2,3}, --verbosity {0,1,2,3}
                        Verbosity level; 0=minimal output, 1=normal output, 2=verbose output, 3=very
                        verbose output
  --settings SETTINGS   The Python path to a settings module, e.g. "myproject.settings.main". If this
                        isn't provided, the DJANGO_SETTINGS_MODULE environment variable will be used.
  --pythonpath PYTHONPATH
                        A directory to add to the Python path, e.g. "/home/djangoprojects/myproject".
  --traceback           Raise on CommandError exceptions.
  --no-color            Don't colorize the command output.
  --force-color         Force colorization of the command output.
  --skip-checks         Skip system checks.
  ```
