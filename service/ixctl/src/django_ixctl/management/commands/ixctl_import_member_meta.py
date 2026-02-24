from __future__ import annotations

import re
from typing import Any

import requests
from django.core.management.base import CommandError
from django.db import transaction
from django_ixctl.models import (
    InternetExchange,
    InternetExchangeMember,
    NetworkMeta,
    Organization,
)

from fullctl.django.management.commands.base import CommandInterface


class Command(CommandInterface):
    """Import member meta-data from an external JSON into ixctl.

    Usage:
        ./manage.py ixctl_import_member_meta <org-slug> <ix-slug> <url>
    """

    help = (
        "Import custom member meta-data (joined, peeringpolicy, reseller, resold, etc.) "
        "from a legacy member list JSON file."
    )

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument("org_slug", help="Organization slug")
        parser.add_argument("ix_slug", help="IX slug")
        parser.add_argument("url", help="URL to JSON list")
        parser.add_argument(
            "--set-logo",
            action="store_true",
            default=False,
            dest="set_logo",
            help="If provided, update NetworkMeta.logo_url from the JSON data. Otherwise existing logos remain unchanged.",
        )

    @transaction.atomic
    def run(self, *args: Any, **options: Any):  # type: ignore[override]
        org_slug = options.get("org_slug")
        ix_slug = options.get("ix_slug")
        url = options.get("url")
        set_logo = options.get("set_logo")

        # Fetch IX
        try:
            org = Organization.objects.get(slug=org_slug)
        except Organization.DoesNotExist:
            raise CommandError(f"Organization '{org_slug}' not found")

        try:
            ix = InternetExchange.objects.get(instance__org=org, slug=ix_slug)
        except InternetExchange.DoesNotExist:
            raise CommandError(
                f"InternetExchange '{ix_slug}' for org '{org_slug}' not found"
            )

        # Fetch JSON data
        self.stdout.write(f"Downloading JSON from {url} …")
        try:
            data = requests.get(url, timeout=30).json()
        except Exception as exc:
            raise CommandError(f"Failed to fetch JSON: {exc}")

        members_data = data.get("member_list", [])
        if not members_data:
            raise CommandError("No member_list found in JSON")

        updated = 0
        skipped_entries: list[tuple[str, str]] = []
        for item in members_data:
            # Extract all IPv4 / IPv6 addresses in the item (they may be space separated)
            addresses = []
            for field in ("ipv4", "ipv6"):
                addr_str = item.get(field) or ""
                addresses += [a for a in re.split(r"\s+", addr_str.strip()) if a]

            if not addresses:
                skipped_entries.append(
                    (item.get("name") or str(item.get("asnum")), "no ip addresses")
                )
                continue

            member_qs = InternetExchangeMember.objects.filter(ix=ix).filter(
                # either ipv4 or ipv6 matches any address
                ipaddr4__in=addresses
            ) | InternetExchangeMember.objects.filter(ix=ix, ipaddr6__in=addresses)

            member = member_qs.first()
            if not member:
                skipped_entries.append(
                    (
                        item.get("name") or str(item.get("asnum")),
                        f"member not found by ip(s): {' '.join(addresses)}",
                    )
                )
                continue

            # Update/merge meta.custom
            custom_fields = {
                "type": item.get("type"),
                "joined": item.get("joined"),
                "peeringpolicy": item.get("peeringpolicy"),
                "reseller": item.get("reseller"),
                "resold": item.get("resold"),
            }

            meta = member.meta or {}
            custom = meta.get("custom", {})
            custom.update(
                {k: v for k, v in custom_fields.items() if v not in (None, "")}
            )
            meta["custom"] = custom
            member.meta = meta
            member.save()

            # Ensure NetworkMeta updated
            net_meta, _ = NetworkMeta.objects.get_or_create(org=org, asn=member.asn)
            # Keep existing name unless new provided
            if item.get("name") and not net_meta.name:
                net_meta.name = item["name"]
            if options.get("set_logo") and item.get("logo"):
                net_meta.logo_url = item["logo"]
            if item.get("url"):
                net_meta.web_url = item["url"]
            net_meta.save()

            updated += 1

        total_skipped = len(skipped_entries)
        self.stdout.write(
            f"Processed {len(members_data)} entries – updated {updated}, skipped {total_skipped}"
        )

        if total_skipped:
            self.stdout.write("Skipped entries:")
            for ident, reason in skipped_entries:
                self.stdout.write(f"  - {ident}: {reason}")
