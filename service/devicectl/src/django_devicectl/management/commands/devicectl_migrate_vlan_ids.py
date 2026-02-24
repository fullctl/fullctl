from django_devicectl.models.devicectl import VirtualPort, Vlan

from fullctl.django.management.commands.base import CommandInterface


class Command(CommandInterface):
    help = "Migrate vlan ids from virtual ports to vlan objects"

    def run(self, *args, **kwargs):
        for virtual_port in VirtualPort.objects.all():
            if not virtual_port.vlan_id or virtual_port.vlan_object_id:
                continue

            vlan, created = Vlan.objects.get_or_create(
                instance=virtual_port.device.instance,
                vlan=virtual_port.vlan_id,
                facility=virtual_port.facility,
                defaults={
                    "name": f"Vlan {virtual_port.vlan_id}",
                    "slug": f"vlan-{virtual_port.vlan_id}",
                    "description": "Automatically created by devicectl_migrate_vlan_ids",
                },
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Created VLAN {vlan.vlan} ({vlan.name}) for {virtual_port}"
                    )
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Assigning VLAN {vlan.vlan} ({vlan.name}) to {virtual_port}"
                )
            )

            virtual_port.vlan_object = vlan
            virtual_port.save()

        self.stdout.write(self.style.SUCCESS("VLAN migration completed."))
