from fullctl.django.management.commands.base import CommandInterface
from fullctl.django.models.concrete import Organization
from fullctl.service_bridge.context import ServiceBridgeContext

from django.core.management.base import CommandError

import django_devicectl.netbox as netbox


class Command(CommandInterface):
    help = "Pull netbox data for specified organization"

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument("org_slug", nargs="?")

        parser.add_argument("--push", action="store_true", help="Push updates to netbox")

        parser.add_argument("--purge", action="store_true", help="Purge devicectl data. This will deleted devices and ports that have references to netbox that no longer exist.")

    def run(self, *args, **kwargs):
        org_slug = kwargs.get("org_slug")
        org = Organization.objects.get(slug=org_slug)

        push = kwargs.get("push")

        commit = kwargs.get("commit")
        purge = kwargs.get("purge")

        if push and not commit:
            raise CommandError("Cannot --push without --commit")

        with ServiceBridgeContext(org):
            self.log_info(f"Pushing updates to netbox for {org_slug}")

            netbox.push(org, full_sync=push, purge=purge)

            self.log_info(f"Pulling netbox data for {org_slug}")

            netbox.pull(org, purge=purge)

            self.log_info(f"Pulled netbox data for {org_slug}")
