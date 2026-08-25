## Prune old events

The `auditctl_prune` management command removes old audit log events from the database. Nothing is deleted without `--commit` (dry-run by default).

### Basic usage

```bash
# Dry-run: see what would be pruned
python manage.py auditctl_prune --max-age 30

# Actually delete events older than 30 days
python manage.py auditctl_prune --max-age 30 --commit
```

If `--max-age` is omitted, the `EVENT_MAX_AGE` setting is used.

### Filtering by object_id

Use `--include` or `--exclude` (mutually exclusive) to filter events by their `object_id` using regex patterns. Bare `*` is expanded to `.*` for glob-style convenience.

```bash
# Prune only high-volume event types, keeping last 30 days
python manage.py auditctl_prune --include ".*(traffic|config/liveness|bgp/stats).*" --max-age 30 --commit

# Prune everything EXCEPT liveness checks
python manage.py auditctl_prune --exclude ".*/config/liveness/.*" --max-age 30 --commit
```

### Pruning tasks alongside events

When `--tasks` is passed, the command also prunes tasks (via `fullctl_manage_tasks prune`) using the same `--include`/`--exclude` pattern matched against the task's `limit_id`. All task statuses are pruned (pending, running, completed, failed, cancelled).

```bash
# Prune events AND tasks for high-volume patterns, keeping last 30 days
python manage.py auditctl_prune --include ".*(traffic|config/liveness|bgp/stats).*" --tasks --max-age 30 --commit
```

### Backing up before deletion

Backup is off by default. Use `--backup` to write pruned events to a JSON file before deleting. Control the output location with `--output-path`.

```bash
python manage.py auditctl_prune --max-age 90 --backup --output-path /tmp/audit-backups --commit
```

### Settings

| Setting | Description | Default |
|---|---|---|
| `EVENT_MAX_AGE` | Default max age in days when `--max-age` is omitted | - |
| `EVENT_PRUNE_BATCH_SIZE` | Rows deleted per batch | 10000 |

### All options

| Option | Description |
|---|---|
| `--max-age`, `-a` | Maximum age of entries to retain in days |
| `--output-path`, `-o` | Path for backup JSON file (default: current directory) |
| `--include` | Only prune events whose `object_id` matches this regex |
| `--exclude` | Only prune events whose `object_id` does NOT match this regex |
| `--tasks` | Also prune tasks with the same filters (all statuses) |
| `--backup` | Back up pruned events to JSON before deleting |
| `--commit` | Actually delete (omit for dry-run) |
