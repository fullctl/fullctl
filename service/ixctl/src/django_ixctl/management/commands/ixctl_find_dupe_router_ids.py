from django.core.management.base import CommandError
from fullctl.django.management.commands.base import CommandInterface

from django_ixctl.models import Routeserver


class Command(CommandInterface):
    help = "Finds instances of route servers within the same organization that share the same router_id value"

    def handle(self, *args, **options):
        # Query to find duplicates by getting all routeservers and checking org
        duplicates = []
        router_ids = Routeserver.handleref.values_list(
            "router_id", flat=True
        ).distinct()

        for router_id in router_ids:
            rs_list = Routeserver.handleref.filter(router_id=router_id)
            orgs = set()
            dupes = []

            for rs in rs_list:
                if rs.ix.instance and rs.ix.instance.org:
                    org = rs.ix.instance.org
                    if org in orgs:
                        dupes.append(rs)
                    orgs.add(org)

            if dupes:
                duplicates.append({"router_id": router_id, "instances": rs_list})

        if duplicates:
            error_msg = ["Found duplicate router_ids within the same organization:"]

            for dupe in duplicates:
                error_msg.append(f"\nDuplicate router_id: {dupe['router_id']}")
                error_msg.append("Affected records:")

                for rs in dupe["instances"]:
                    org = rs.ix.instance.org if rs.ix.instance else "No org"
                    error_msg.append(f"- ID: {rs.id}, IX: {rs.ix_id}, Org: {org}")

                error_msg.append("-" * 40)

            raise CommandError("\n".join(error_msg))

        self.stdout.write("No duplicate router_ids found within organizations")
