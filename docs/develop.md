
### Database

This uses a common database between fullctl services

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

### TODO

Decide whether to use a common `.env` file (like aaactl_web) or use one from the service directory (like ixctl_web).
