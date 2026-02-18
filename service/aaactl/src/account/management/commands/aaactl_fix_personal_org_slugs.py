from fullctl.django.management.commands.base import CommandInterface

from account.models import Organization, generate_org_slug


class Command(CommandInterface):

    """
    Loops through all personal orgs and randomizes their slugs and sets
    org name to the owning user's name
    """

    def run(self, *args, **kwargs):
        # update all orgs
        for org in Organization.objects.exclude(user__isnull=True):
            self.log_info(f"Fixing personal org {org.id} {org.name} {org.slug}")
            org.name = org.user.username
            org.slug = generate_org_slug()
            org.save()
