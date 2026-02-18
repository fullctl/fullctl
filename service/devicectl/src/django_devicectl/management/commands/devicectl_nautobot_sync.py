from fullctl.django.management.commands.base import CommandInterface
from fullctl.django.models.concrete import Organization
from fullctl.service_bridge.context import ServiceBridgeContext

import django_devicectl.nautobot as nautobot


class Command(CommandInterface):
    help = "Pull nautobot data for specified organization"

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument("org_slug", nargs="?")

    def run(self, *args, **kwargs):
        org_slug = kwargs.get("org_slug")
        org = Organization.objects.get(slug=org_slug)

        with ServiceBridgeContext(org):
            self.log_info(f"Pushing updates to nautobot for {org_slug}")

            nautobot.push(org)

            self.log_info(f"Pulling nautobot data for {org_slug}")

            nautobot.pull(org)

            self.log_info(f"Pulled nautobot data for {org_slug}")
