import fullctl.service_bridge.devicectl as devicectl
import structlog
from fullctl.django.models import Organization, Task
from fullctl.django.tasks import register
from fullctl.service_bridge.client import ServiceBridgeError
from fullctl.service_bridge.context import (
    service_available,
)

import django_ixctl.models.ixctl as models
from django_ixctl import port_automation
from django_ixctl.schema import IXLanConfig

log = structlog.get_logger(__name__)


class PortAutomationBase:
    @property
    def devicectl_available(self) -> bool:
        return service_available(self.org, "devicectl")


class MemberValidationMixin(PortAutomationBase):
    class TaskMeta:
        limit = 10

    @classmethod
    def create_task(cls, org, ix_id, member_data, **kwargs):
        """
        Create a member validation task
        """
        return super().create_task(
            org=org, ix_id=ix_id, member_data=member_data, **kwargs
        )

    @property
    def ix_id(self):
        return self.param["kwargs"]["ix_id"]

    @property
    def ix(self):
        return models.InternetExchange.objects.get(pk=self.ix_id)

    @property
    def member_data(self) -> dict:
        return self.param["kwargs"]["member_data"]

    @property
    def generate_limit_id(self) -> str:
        return f"{self.ix_id}"

    @property
    def ixlan_config(self) -> IXLanConfig:
        return port_automation.get_ix_lan_config(self.ix)

    def run_validation_task(self, *args, **kwargs):
        return {}

    def run(self, *args, **kwargs):
        try:
            return self.run_validation_task(*args, **kwargs)
        except Exception as e:
            log.error("Validation task failed", exc_info=e)
            return {"valid": False, "message": "Validation task failed"}


@register
class GetNextAvailableIPAddresses(MemberValidationMixin, Task):
    """
    This task gets the next available IPv4 address from the backend system
    And also generates an IPv6 address using the last octet of the IPv4 address.
    """

    class Meta:
        proxy = True

    class TaskMeta(MemberValidationMixin.TaskMeta):
        result_type = dict

    class HandleRef:
        tag = "task_get_next_ip_addresses"


@register
class VerifyCaseNumber(MemberValidationMixin, Task):
    """
    This task verifies the organization, by checking the entered
    case number against the work order in the backend system.

    This task is only run if MEMBER_CASE_NUMBERS_ENABLED is True
    """

    class Meta:
        proxy = True

    class TaskMeta(MemberValidationMixin.TaskMeta):
        result_type = dict

    class HandleRef:
        tag = "task_verify_case_number"


@register
class MemberPortUpdate(PortAutomationBase, Task):
    """
    Will run some tasks after member ports have changed.

    This is triggered during member creation, and memeber updates
    that change the port assignment for the member either through
    LAG augmentation (quantity of physicak ports change) or port resize (complete port replacement).
    """

    class Meta:
        proxy = True

    class TaskMeta(MemberValidationMixin.TaskMeta):
        result_type = dict

    class HandleRef:
        tag = "task_member_port_update"

    @classmethod
    def create_task(
        cls, org: Organization, member_id: int, case_number: str = None, **kwargs
    ):
        """
        Create a member creation finalize task
        """
        return super().create_task(
            org=org, member_id=member_id, case_number=case_number, **kwargs
        )

    @property
    def member_id(self) -> int:
        return self.param["kwargs"]["member_id"]

    @property
    def member(self) -> models.InternetExchangeMember:
        if hasattr(self, "_member"):
            return self._member
        self._member = models.InternetExchangeMember.objects.get(pk=self.member_id)
        models.InternetExchangeMember.preload_ports(self.org.slug, [self._member])
        return self._member

    @property
    def case_number(self) -> str:
        return self.param["kwargs"].get("case_number")

    def run(self, *args, **kwargs):
        r = {}
        return r


@register
class MemberDeletionFinalize(PortAutomationBase, Task):
    """
    Will run some final cleanup after a member is deleted depending
    on what services are available for the org.
    """

    class Meta:
        proxy = True

    class TaskMeta(MemberValidationMixin.TaskMeta):
        result_type = dict

    class HandleRef:
        tag = "task_member_deletion_finalize"

    @classmethod
    def org_has_services(cls, org: Organization) -> bool:
        return service_available(org, "devicectl")

    @classmethod
    def create_task(cls, org: Organization, member_data: dict, **kwargs):
        """
        Create a member deletion finalize task
        """
        return super().create_task(org=org, member=member_data, **kwargs)

    @property
    def member(self) -> dict:
        return self.param["kwargs"]["member"]

    def run(self, *args, **kwargs):
        r = {}

        if self.devicectl_available:
            r["devicectl"] = self.run_devicectl_cleanup(*args, **kwargs)

        if not r:
            return {"status": "ok", "message": "No services to cleanup"}

        return r

    def run_devicectl_cleanup(self, *args, **kwargs):
        """
        Mark physical ports as available
        """

        try:
            devicectl.Port().unassign(self.member["port"])
        except ServiceBridgeError as e:
            if e.status == 404:
                return {"status": "ok", "message": "Port already unassigned"}
            else:
                raise

        return {
            "status": "ok",
            "message": "Sent request to devicectl to unassign port.",
        }
