import json
import os
from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone
from fullctl.django.management.commands.base import CommandInterface

from django_auditctl.models.auditctl import Event


class Command(CommandInterface):
    help = 'Prune old audit log event entries'

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('-a', '--max-age', type=int, help='Maximum age of entries to retain in days. If not specified `EVENT_MAX_AGE` will be used.')
        parser.add_argument('-o', '--output-path', type=str, help='Path where the dumped JSON will be stored. If omitted, the current directory will be used.')

    def run(self, *args, **kwargs):
        max_age = kwargs.get('max_age')
        if max_age is None:
            max_age = settings.EVENT_MAX_AGE

        max_age_fmt = f'{max_age} days'

        cutoff_date = timezone.now() - timedelta(days=max_age)

        self.log_info(f"Pruning entries older than {max_age_fmt} ({cutoff_date})")

        # Fetch Event entries older than cutoff_date
        old_entries = Event.objects.filter(created__lt=cutoff_date)
        if not old_entries.exists():
            self.log_info('No Events to prune')
            return

        # Dump entries as JSON
        export_data = [entry.to_dict() for entry in old_entries]

        output_path = kwargs.get('output_path', '')
        if not output_path:
            output_path = os.path.dirname(os.path.abspath(__file__))

        if self.commit:
            self.log_info(f'Backing up entries to {output_path}')
        else:
            self.log_info(f'Would back up entries to {output_path}')

        date = cutoff_date.strftime('%Y-%m-%d_%H:%M:%S')
        file_path = os.path.join(output_path, f'pruned_audit_log_{date}.json')

        if self.commit:
            with open(file_path, 'w') as f:
                json.dump(export_data, f, indent=4)
            self.log_info(f'Entries backed up to {file_path}')

        # Get entry count
        entry_count = old_entries.count()

        # Delete entries older than cutoff_date
        old_entries.delete()

        self.log_info(f"Pruned {entry_count} entries.")
