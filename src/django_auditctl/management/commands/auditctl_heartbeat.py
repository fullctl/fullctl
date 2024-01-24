from fullctl.django.management.commands.base import CommandInterface

import django_auditctl.heartbeat as heartbeat


class Command(CommandInterface):
    help = "Checks and handles notifications for events that are no longer occurring within a specified idle time."

    def run(self, *args, **options):
        heartbeat.process_overdue()
