import fullctl.service_bridge.ixctl as ixctl
import fullctl.service_bridge.devicectl as devicectl
from fullctl.django.models.concrete import Task, Organization
from fullctl.django.tasks import register
import django_peerctl.utils as utils


import structlog
logger = structlog.getLogger("django_structlog")


@register
class SyncMacAddress(Task):

    """
    Sync the port mac address to ixctl
    """

    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_sync_mac_address"

    def run(self, asn:int, ip4:str, mac_addresses: list[str], *args, **kwargs):
        ixctl.InternetExchangeMember().set_mac_address(
            asn, ip4, mac_addresses, source="peerctl"
        )


@register
class SyncASSet(Task):

    """
    Sync the network as-set to ixctl
    """

    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_sync_asset"

    def run(self, member_id, as_macro, *args, **kwargs):
        ixctl.InternetExchangeMember().set_as_macro(
            member_id, as_macro, source="peerctl"
        )


@register
class SyncRouteServerMD5(Task):

    """
    Sync the network's route server md5 to ixctl
    """

    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_sync_md5"

    def run(self, asn, md5, ix_id, *args, **kwargs):
        return ixctl.InternetExchangeMember().set_route_server_md5(
            asn, md5, ix_id, source="peerctl"
        )


@register
class SyncIsRsPeer(Task):

    """
    Syncs the network's route server peer status to ixctl for a member port
    """

    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_sync_is_rs_peer"

    def run(self, asn, ip4, is_rs_peer, *args, **kwargs):
        # get the member object

        member = ixctl.InternetExchangeMember().first(ip=ip4, asn=asn, ix_verified=True)

        if not member:
            return f"no member found for {asn} {ip4} at any verified ix"

        # send a partial update to ixctl to set the is_rs_peer
        # value accordingly

        ixctl.InternetExchangeMember().partial_update(
            member, {"is_rs_peer": is_rs_peer}
        )

        return f"updated {member.id} is_rs_peer to {is_rs_peer}"


@register
class SyncStatus(Task):

    """
    Syncs the network's port status to ixctl for a member port
    """

    class Meta:
        proxy = True

    class HandleRef:
        tag = "task_sync_status"

    def run(self, asn, ref_id, status, *args, **kwargs):

        ref_source, ref_object_id = ref_id.split(":")

        if ref_source != "ixctl":
            raise Exception("Only ixctl sourced ports can be updated")

        member = ixctl.InternetExchangeMember().first(id=ref_object_id)

        if not member:
            return f"no member found for for ref_id {ref_id}"

        ixctl.InternetExchangeMember().set_ports_status(
            member_id=member.id,
            member_port=member.port,
            status=status,
        )

        return f"updated {member.id=} {member.port=} to {status=}"


@register
class SyncDevicePorts(Task):

    """
    Sync devices and ports from devicectl to port info objects in peerctl

    This will call utils.devicectl_create_devices for all networks owned by an
    organziation.
    """

    class Meta:
        proxy = True

    class TaskMeta:
        limit = 1

    class HandleRef:
        tag = "task_sync_device_ports"

    def run(self, *args, **kwargs):
        from django_peerctl.utils import devicectl_create_devices

        devicectl_create_devices(self.org, [net.asn for net in self.org.net_set.all()])

    @property
    def generate_limit_id(self):
        return self.org_id


@register
class RequestDummyPorts(Task):

    """
    Request dummy ports from devicectl
    """

    class Meta:
        proxy = True
        verbose_name = "Request Dummy Ports"
        verbose_name_plural = "Request Dummy Ports"

    class TaskMeta:
        limit = 1

    class HandleRef:
        tag = "task_request_dummy_ports"
    

    @classmethod
    def create_task(cls, org:Organization, asns:list[int], **kwargs):
        kwargs.pop("org", None)
        return super().create_task(org=org, asns=asns, **kwargs)

    @property
    def generate_limit_id(self):
        return self.org_id

    def run(self, *args, **kwargs):

        asns:list[int] = kwargs.get("asns", [])

        for asn in asns:
            self.claim_asn(asn)

        # now we need to request dummy ports for the asns
        # this is already smart enough to only do this for ports currently
        # missing, so we can just call it with the asns
        utils.devicectl_create_devices(self.org, asns)


    def claim_asn(self, asn:int):
        
        org = self.org

        # this will raise an ASNClaimed exception if the asn is already claimed
        # otherwise the network will be created and claimed by the org

        # claim issues need to be manually followed up, so the error is raised
        # as is and the task will fail
        utils.get_network(asn, org)



