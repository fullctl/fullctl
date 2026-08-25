"""
Scan for and remove duplicate cached Request rows.

Duplicates can exist on any environment that predates the (source, url)
uniqueness constraint (they were produced by a race between concurrent
first-fetches). The constraint migration aborts on deploy if any remain, so
this command is meant to be run once, per environment, before that migration.

By default it runs in pretend mode and only reports what it would do; pass
`--commit` to actually delete. Covers both request-cache tables:

    prefix_meta.Request        -> prefix_meta_request  (ripestat, arin-whowas,
                                                        rir, irr, apnic, regctl,
                                                        ip2location, prefixmetad)
    concrete.meta.Request      -> request              (arin-api)
"""

from django.db.models import Count
from prefix_meta.models import Request as PrefixMetaRequest

from fullctl.django.management.commands.base import CommandInterface
from fullctl.django.models.concrete.meta import Request as GenericRequest

# cache identity == (source, url): url is derived from the request target and
# type is constant per source, so url determines type; both columns are
# non-null, so there is no NULL hole. Matches the UNIQUE constraint.
KEY_FIELDS = ["source", "url"]

# each model is one physical cache table; every source is a proxy on one of
# them -- prefix_meta_request (ripestat, arin-whowas, rir, irr, apnic, regctl,
# ip2location, prefixmetad) and request (arin-api).
REQUEST_MODELS = [PrefixMetaRequest, GenericRequest]


class Command(CommandInterface):
    help = "Remove duplicate cached Request rows (keyed on source + url)."

    # default to pretend mode; --commit is added by CommandInterface
    always_commit = False
    # this is an operational cleanup, not a queueable task
    queue_allowed = False

    def run(self, *args, **kwargs):
        for model in REQUEST_MODELS:
            self.dedupe(model)

    def dedupe(self, model):
        table = model._meta.db_table

        groups = list(
            model.objects.values(*KEY_FIELDS)
            .annotate(n=Count("id"))
            .filter(n__gt=1)
            .order_by("-n")
        )

        if not groups:
            self.log_info(f"[{table}] no duplicate cache keys")
            return

        removed = 0
        for group in groups:
            key = {field: group[field] for field in KEY_FIELDS}
            rows = list(
                model.objects.filter(**key)
                .order_by("-updated", "-id")
                .values("id", "count")
            )
            # keep the freshest row (the one get_cache() serves) and roll the
            # split hit count back into it; drop the rest (their response and
            # attachments cascade).
            keep_id = rows[0]["id"]
            dupe_ids = [row["id"] for row in rows[1:]]
            summed = sum(row["count"] for row in rows)

            model.objects.filter(id=keep_id).update(count=summed)
            model.objects.filter(id__in=dupe_ids).delete()

            removed += len(dupe_ids)
            self.log_info(f"[{table}] key={key} keep={keep_id} removed={dupe_ids}")

        self.log_info(f"[{table}] {removed} duplicate row(s) removed")
