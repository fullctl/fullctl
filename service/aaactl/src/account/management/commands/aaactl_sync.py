import traceback

from django.contrib.auth import get_user_model
from fullctl.django.management.commands.base import CommandInterface

from account.models import Organization
from applications.models import Service
from applications.service_bridge import Bridge


class Command(CommandInterface):

    """
    Sync user and organization information to connected
    service applications
    """

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument(
            "type", type=str, choices=("org", "user", "org_user", "all")
        )
        parser.add_argument("id", type=int)

    def run(self, *args, **kwargs):
        typ = kwargs.get("type")
        pk = kwargs.get("id")

        for svc in Service.objects.filter(status="ok"):
            if not svc.api_url:
                self.log_info(f"No api url specified for {svc.name}, skipping ..")
                continue

            fn = getattr(self, f"sync_{typ}")

            if self.commit:
                try:
                    fn(svc, pk)
                except Exception as e:
                    self.log_error(f"Error syncing {typ} {pk} to {svc.name}: {e}")
                    self.stdout.write(traceback.format_exc())
                    continue

    def sync_org(self, svc, pk):
        self.log_info(f"Syncing org {pk} to {svc.name}")
        org = Organization.objects.get(pk=pk)
        bridge = Bridge(svc, org)
        bridge.sync_org()

    def sync_user(self, svc, pk):
        self.log_info(f"Syncing user {pk} to {svc.name}")
        user = get_user_model().objects.get(pk=pk)
        bridge = Bridge(svc, None, user=user)
        bridge.sync_user()

    def sync_org_user(self, svc, pk):
        self.log_info(f"Syncing org user {pk} to {svc.name}")
        user = get_user_model().objects.get(pk=pk)
        bridge = Bridge(svc, None, user=user)
        bridge.sync_org_user()

    def sync_all(self, svc, pk):
        """
        Syncs all organizations, users and organization members
        to a service
        """

        for org in Organization.objects.all():
            self.sync_org(svc, org.id)

        for user in get_user_model().objects.all():
            self.sync_user(svc, user.id)
            self.sync_org_user(svc, user.id)
