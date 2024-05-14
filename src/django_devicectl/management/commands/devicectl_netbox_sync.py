from fullctl.django.management.commands.base import CommandInterface
from fullctl.django.models.concrete import Organization
from fullctl.service_bridge.context import ServiceBridgeContext

import django_devicectl.netbox as netbox


class Command(CommandInterface):
    help = "Pull netbox data for specified organization"

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument("org_slug", nargs="?")

    def run(self, *args, **kwargs):
        org_slug = kwargs.get("org_slug")
        org = Organization.objects.get(slug=org_slug)

        with ServiceBridgeContext(org):
            self.log_info(f"Pushing updates to netbox for {org_slug}")

            netbox.push(org)

            self.log_info(f"Pulling netbox data for {org_slug}")

            netbox.pull(org)

            self.log_info(f"Pulled netbox data for {org_slug}")
