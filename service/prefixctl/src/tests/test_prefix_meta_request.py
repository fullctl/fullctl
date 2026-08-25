import pytest
from django.core.management import call_command
from django.db import IntegrityError, connection, transaction
from prefix_meta.models import Request


def test_request_unique_cache_key_constraint(db):
    """
    FC-6982: a duplicate (source, url) row must raise IntegrityError. Guards
    the prefixctl wiring -- prefix_meta.Request inherits the constraint from
    the abstract base and the migration created it on the shared
    prefix_meta_request table (all sources are proxies on it).
    """
    params = dict(
        prefix="204.28.216.0/22",
        url="http://example.test/whois?resource=204.28.216.0/22",
        source="ripestat-historicalwhois",
        type="live",
    )
    Request.objects.create(http_status=200, **params)

    with pytest.raises(IntegrityError):
        # wrapped in atomic() so the failed INSERT doesn't poison the
        # surrounding test transaction
        with transaction.atomic():
            Request.objects.create(http_status=200, **params)


def _drop_cache_key_constraint():
    """
    Planting the pre-constraint duplicates that the dedupe command cleans up
    means getting past the (source, url) UNIQUE constraint, so drop it first.
    The surrounding test transaction rolls the drop back afterwards.
    """
    constraint = next(
        c for c in Request._meta.constraints if c.name.endswith("unique_cache_key")
    )
    with connection.schema_editor() as editor:
        editor.remove_constraint(Request, constraint)


def test_prefixctl_dedupe_request_cache(db):
    """
    The dedupe command collapses duplicate (source, url) rows to a single row
    -- keeping the freshest and rolling the split hit count into it -- and
    leaves distinct rows untouched. Preview (no --commit) changes nothing.
    """
    _drop_cache_key_constraint()

    key = dict(
        source="ripestat-historicalwhois",
        url="http://example.test/whois?resource=10.0.0.0/24",
    )
    Request.objects.create(
        prefix="10.0.0.0/24", type="live", http_status=200, count=3, **key
    )
    Request.objects.create(
        prefix="10.0.0.0/24", type="live", http_status=200, count=4, **key
    )
    # a distinct cache key that must be left untouched
    keeper = Request.objects.create(
        prefix="10.0.1.0/24",
        url="http://example.test/whois?resource=10.0.1.0/24",
        source="ripestat-historicalwhois",
        type="live",
        http_status=200,
        count=1,
    )

    # preview (no --commit) must not delete anything
    call_command("prefixctl_dedupe_request_cache")
    assert Request.objects.filter(**key).count() == 2

    # --commit collapses the dupes to one row and sums the hit count (3 + 4)
    call_command("prefixctl_dedupe_request_cache", "--commit")
    survivors = Request.objects.filter(**key)
    assert survivors.count() == 1
    assert survivors.first().count == 7
    assert Request.objects.filter(pk=keeper.pk).exists()
