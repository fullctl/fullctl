from django.core.management.base import CommandError
from django_ixctl.models import InternetExchange, InternetExchangeMember

from fullctl.django.management.commands.base import CommandInterface
from fullctl.django.models.concrete import Organization


class Command(CommandInterface):
    help = "Fixes the port configuration intent values of existing internet exchange members, according to the source of truth that exists in devicectl"

    def add_arguments(self, parser):
        super().add_arguments(parser)

        # CAn either do a specific exchange or all exchanges in an organization
        parser.add_argument(
            "--org",
            help="Organization slug - if specified, will fix all exchanges in the organization",
        )
        parser.add_argument(
            "--ix",
            help="Internet Exchange slug - if specified, will fix only this exchange",
        )

        # Speed may not be set on the devicectl ports, provide a fallback in Gb/s
        parser.add_argument(
            "--speed",
            type=int,
            default=10,
            help="Fallback speed in Gb/s for ports that do not have a speed set in devicectl",
        )

    def run(self, *args, **kwargs):
        # org must always be specified
        org_slug = kwargs.get("org")

        self.speed_fallback = kwargs.get("speed")

        if not org_slug:
            raise CommandError("Organization slug must be specified")

        try:
            org = Organization.objects.get(slug=org_slug)
        except Organization.DoesNotExist:
            raise CommandError(f"Organization {org_slug} does not exist")

        ix_slug = kwargs.get("ix")

        if ix_slug:
            try:
                ix = InternetExchange.objects.get(instance__org=org, slug=ix_slug)
            except InternetExchange.DoesNotExist:
                raise CommandError(
                    f"Internet Exchange {ix_slug} does not exist in organization {org_slug}"
                )
            self.fix_exchange(org, ix)
        else:
            self.fix_org(org)

    def fix_org(self, org: Organization):
        exchanges = InternetExchange.objects.filter(instance__org=org)
        self.log_info(f"Fixing {len(exchanges)} exchanges for {org.slug}")
        for ix in exchanges:
            self.fix_exchange(org, ix)

    def fix_exchange(self, org: Organization, ix: InternetExchange):
        members = InternetExchangeMember.objects.filter(ix=ix, port__gt=0)

        self.log_info(f"Checking {len(members)} members for {ix.slug}")

        InternetExchangeMember.preload_ports(org, members)

        save = []

        for member in members:
            port_size = self.speed_fallback

            for physical_port in member.port.object.physical_ports:
                if physical_port.get("size"):
                    port_size = physical_port.get("size")
                    break

            sot_port_quantity = len(member.physical_ports)
            sot_lag = sot_port_quantity > 1
            sot_port_size = port_size

            # update `port_quantity`, `lag`, and `port_size` if they are different
            changes = False
            if member.port_quantity != sot_port_quantity:
                changes = True
                self.log_info(
                    f"{member} port_quantity: {member.port_quantity} -> {sot_port_quantity}"
                )
                member.port_quantity = sot_port_quantity
            if member.lag != sot_lag:
                changes = True
                self.log_info(f"{member} lag: {member.lag} -> {sot_lag}")
                member.lag = sot_lag
            if member.port_size != sot_port_size:
                changes = True
                self.log_info(
                    f"{member} port_size: {member.port_size} -> {sot_port_size}"
                )
                member.port_size = sot_port_size
            if changes:
                save.append(member)

        if save:
            self.log_info(f"Saving {len(save)} members for {ix.slug}")
            InternetExchangeMember.objects.bulk_update(
                save, ["port_quantity", "lag", "port_size"]
            )
