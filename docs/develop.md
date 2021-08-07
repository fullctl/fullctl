
## fullctl services development instance

## Code Quality

Install pre-commit with (for running before push)
```sh
poetry run pre-commit install -t pre-push
```

Or manually run with
```sh
poetry run pre-commit run --all-files
```

## Poetry

To update package deps, use

```sh
poetry lock
poetry install
poetry run pre-commit clean
```

## Database

This uses a common database server between fullctl services, each service still has it's own database.

To start it separately:

```sh
poetry run Ctl/dev/compose.sh up postgres
```

#### Backups

Backup dev database
```sh
poetry run Ctl/dev/exec.sh postgres bash -c 'pg_dumpall -c -U ${POSTGRES_USER}' | xz > fulldb-$(date +%Y%m%d"-"%H%M%S).sql.xz
```

Restore:
```sh
cat $FILE | poetry run Ctl/dev/exec.sh postgres bash -c 'psql -U ${POSTGRES_USER}'
```
#### Snippets

```sh
# add psql
apk add postgresql-client

# on postgres for superuser
PGPASSWORD=$DATABASE_PASSWORD psql -h postgres -U $POSTGRES_USER

# service user
PGPASSWORD=$DATABASE_PASSWORD psql -h postgres -U $DATABASE_USER
```

Check perms on table

```sql
SELECT grantee, privilege_type FROM information_schema.role_table_grants WHERE table_name='django_migrations';
```

## Services

fullctl expects all used services to be cloned in it's parent dir. For example:

```
github.com/fullctl/
  fullctl/
  aaactl/
  ixctl/
  prefixctl/
```

To start individually, for example `aaactl`
semanage port -m -t http_port_t -p tcp 8001


```sh
# change the port it listens on if needed
# export AAACTL_PORT=7002
poetry run Ctl/dev/compose.sh up aaactl_web
```


### Bumping release

```sh
poetry run ctl version bump .
poetry lock
git commit -am "lock, bump version"
poetry run ctl deploy_dev
```

### TODO
