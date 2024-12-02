from fullctl.django.models import Organization, Task
from fullctl.django.tasks import register

from django_devicectl.models import PhysicalPort, Port


@register
class AssignPort(Task):
    """
    Runs tasks for port assignment.

    When a port is assigned to a virtual port, the port and port info objects
    are created and the physical ports are marked as unavailable.

    Currently this implements only against FNT services, if available for the organization.
    """

    class Meta:
        proxy = True

    class TaskMeta:
        result_type = dict

    class HandleRef:
        tag = "task_assign_port"

    @classmethod
    def create_task(
        cls, org: Organization, physical_ports: list[PhysicalPort], port: Port, **kwargs
    ):

        return super().create_task(
            org=org,
            physical_ports=[p.id for p in physical_ports],
            port_id=port.id,
            **kwargs
        )

    @property
    def port(self) -> Port:
        return Port.objects.get(id=self.param["kwargs"]["port_id"])

    @property
    def physical_ports(self) -> list[PhysicalPort]:
        return list(
            PhysicalPort.objects.filter(id__in=self.param["kwargs"]["physical_ports"])
        )

    def run(self, *args, **kwargs):
        r = {}

        # Create port and port info objects
        for physical_port in self.physical_ports:
            physical_port.set_logical_port(self.port.virtual_port.logical_port)

        return r


@register
class UnassignPort(Task):
    """
    Runs finalization tasks for port unassignment.

    When a port is unassigned its virtual port, port and port info objects
    are deleted. Marking the physical ports as available is done in this task.

    Currently this implements only against FNT services, if available for the organization.
    """

    class Meta:
        proxy = True

    class TaskMeta:
        result_type = dict

    class HandleRef:
        tag = "task_unassign_port"

    @classmethod
    def create_task(
        cls,
        org: Organization,
        port: Port | None = None,
        physical_ports: list[PhysicalPort] | None = None,
        **kwargs
    ):

        # if both port and physical_ports are provided, raise an error
        if port and physical_ports:
            raise ValueError(
                "Both port and physical_ports cannot be provided together."
            )

        return super().create_task(
            org=org,
            port_id=port.id if port else None,
            physical_ports=[p.id for p in physical_ports] if physical_ports else None,
            **kwargs
        )

    @property
    def port(self) -> Port:
        if not self.param["kwargs"]["port_id"]:
            return None
        return Port.objects.get(id=self.param["kwargs"]["port_id"])

    @property
    def physical_ports(self) -> list[PhysicalPort]:
        if self.param["kwargs"]["physical_ports"]:
            return list(
                PhysicalPort.objects.filter(
                    id__in=self.param["kwargs"]["physical_ports"]
                )
            )
        return list(self.port.virtual_port.logical_port.physical_ports.all())

    def run(self, *args, **kwargs):

        r = {}

        if self.port:
            # Port instance was provided, delete the port and its related objects
            self.port.delete_chain()
            r["devicectl"] = {
                "status": "ok",
                "message": "Port unassignment tasks completed.",
            }

        else:
            for physical_port in self.physical_ports:
                physical_port.unassign()

        return r
