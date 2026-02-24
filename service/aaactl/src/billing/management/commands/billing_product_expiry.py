from billing.models import OrganizationProduct
from django.utils import timezone

from fullctl.django.management.commands.base import CommandInterface


class Command(CommandInterface):
    help = "Handles organization product access expiry"

    def run(self, *args, **kwargs):
        qset = OrganizationProduct.objects.filter(expires__lt=timezone.now())
        for org_prod in qset:
            self.log_info(f"Expiring {org_prod.product} for {org_prod.org}")
            org_prod.delete()
