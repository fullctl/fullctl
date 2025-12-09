from django.contrib.auth import get_user_model
from django_grainy.util import check_permissions
from fullctl.django.management.commands.base import CommandInterface

from account.models import Organization, OrganizationRole, Role


class Command(CommandInterface):

    """
    Assigns users default oragnization roles as needed
    """

    def run(self, *args, **kwargs):
        for org in Organization.objects.all():
            self.assign_roles(org)

    def assign_roles(self, org):
        for org_user in org.org_user_set.all():
            user = get_user_model().objects.get(id=org_user.user.id)

            org_role = OrganizationRole.objects.filter(user=user, org=org)

            if org_role.exists():
                continue

            if check_permissions(user, org, "c") or org.user == user:
                role = Role.objects.get(name="Admin")
            else:
                role = Role.objects.get(name="Member")

            self.log_info(f"assigning role {role} to {user} in {org} ({org.id})")

            OrganizationRole.objects.get_or_create(org=org, user=user, role=role)
