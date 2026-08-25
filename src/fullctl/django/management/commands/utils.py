import re

from django.core.management.base import CommandError
from django.db import connection
from django.utils import timezone

# A `*` is only treated as a glob wildcard where a regex quantifier cannot
# legally appear: at the start of the pattern, or directly after `(`, `|` or
# `/`. Anywhere else it is a quantifier for the preceding token and is left
# alone -- these patterns select rows for deletion, so silently widening
# `\d*` into `\d.*` is worse than not supporting the shorthand there.
_GLOB_STAR = re.compile(r"(?P<lead>^|[(|/])\*")


def pattern_to_regex(pattern):
    """
    Convert a user-supplied pattern to a regex string.

    `**` is collapsed to `.*`, except after a `.` where it would already be a
    repeated quantifier. A single `*` is expanded to `.*` only in positions
    where it cannot be a regex quantifier (start of pattern, or after `(`,
    `|` or `/`), so glob-style shorthand and full regex syntax can be mixed
    without the shorthand rewriting quantifiers such as `\\d*` or `[a-z]*`.

    Anything left ambiguous stays as written and is rejected by
    `validate_regex` rather than silently broadened -- these patterns select
    rows for deletion.
    """
    pattern = re.sub(r"(?<!\.)\*{2,}", ".*", pattern)
    return _GLOB_STAR.sub(lambda m: f"{m.group('lead')}.*", pattern)


def validate_regex(pattern, label):
    """
    Validate that a pattern compiles as a valid regex.

    Raises CommandError with a clear message on failure, so a bad pattern
    from the command line reports as a command error rather than a traceback.
    """
    try:
        re.compile(pattern)
    except re.error as exc:
        raise CommandError(f"Invalid regex for --{label}: {pattern!r} ({exc})")


def get_fk_children(table_name):
    """
    Query pg_constraint for all tables that have a FK referencing table_name.

    Returns a list of (child_table, child_column) tuples.
    Only works on PostgreSQL; returns an empty list on other backends.
    """
    if connection.vendor != "postgresql":
        return []

    sql = """
        SELECT cl.relname, a.attname
        FROM pg_constraint con
        JOIN pg_class cl ON con.conrelid = cl.oid
        JOIN pg_class pcl ON con.confrelid = pcl.oid
        JOIN pg_attribute a ON a.attrelid = cl.oid AND a.attnum = ANY(con.conkey)
        WHERE con.contype = 'f' AND pcl.relname = %s
    """
    with connection.cursor() as cursor:
        cursor.execute(sql, [table_name])
        return cursor.fetchall()


def pg_batch_delete_sql(table, inner_sql, fk_children):
    """
    Build the PostgreSQL batched-delete statement for `table`.

    `inner_sql` selects the ids of one batch; `fk_children` is the
    `get_fk_children(table)` result.

    Child rows are removed by data-modifying CTEs rather than by relying on
    the database to cascade, because Django declares its FKs without
    ON DELETE CASCADE and does the cascading in Python.

    A self-referencing FK (e.g. ``fullctl_task.parent_id``) is not handled as
    a flat cascade: deleting the children directly would orphan *their* child
    rows in the other tables and abort the statement on an FK violation. Such
    columns instead drive a recursive CTE that expands the batch to its full
    descendant closure, so every table's cascade covers the descendants too.
    """
    self_fk_cols = [col for child_table, col in fk_children if child_table == table]
    child_fks = [
        (child_table, col) for child_table, col in fk_children if child_table != table
    ]

    if self_fk_cols:
        # UNION (not UNION ALL) so a cycle in the parent chain terminates.
        join_cond = " OR ".join(f'child."{col}" = closure."id"' for col in self_fk_cols)
        ctes = [
            f"WITH RECURSIVE batch AS MATERIALIZED ({inner_sql})",
            f'closure AS (SELECT "id" FROM batch UNION '
            f'SELECT child."id" FROM "{table}" child '
            f"JOIN closure ON ({join_cond}))",
        ]
        target = "closure"
    else:
        ctes = [f"WITH batch AS MATERIALIZED ({inner_sql})"]
        target = "batch"

    ctes += [
        f'cascade_{i} AS (DELETE FROM "{child_table}" '
        f'WHERE "{col}" IN (SELECT "id" FROM {target}))'
        for i, (child_table, col) in enumerate(child_fks)
    ]

    return (
        f"{', '.join(ctes)} "
        f'DELETE FROM "{table}" USING {target} '
        f'WHERE "{table}"."id" = {target}."id"'
    )


def batched_raw_delete(queryset, batch_size, log_info, label="rows"):
    """
    Delete everything matched by `queryset` in batches of raw SQL.

    Bypasses the ORM collector so that pruning a very large table does not
    have to load ids into memory. Returns the total number of rows deleted.

    `log_info` is called once per batch with a progress line; `label` names
    the deleted objects in it.
    """
    table = queryset.model._meta.db_table
    is_pg = connection.vendor == "postgresql"
    fk_children = get_fk_children(table) if is_pg else []

    total_deleted = 0
    batch_num = 0

    while True:
        inner_qs = queryset.values("id")[:batch_size]
        inner_sql, inner_params = inner_qs.query.get_compiler(
            using=queryset.db
        ).as_sql()

        if is_pg:
            delete_sql = pg_batch_delete_sql(table, inner_sql, fk_children)
        else:
            delete_sql = f'DELETE FROM "{table}" WHERE "id" IN ({inner_sql})'

        t_start = timezone.now()
        with connection.cursor() as cursor:
            cursor.execute(delete_sql, inner_params)
            deleted = cursor.rowcount
        elapsed = (timezone.now() - t_start).total_seconds()

        if deleted == 0:
            break

        batch_num += 1
        total_deleted += deleted
        log_info(
            f"Batch {batch_num}: deleted {deleted} {label} in {elapsed:.2f}s "
            f"(total: {total_deleted})"
        )

    return total_deleted
