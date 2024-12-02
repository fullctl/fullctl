from django.contrib import admin
from django.utils.safestring import mark_safe

# from django.utils.translation import gettext as _
from django_handleref.admin import VersionAdmin
from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import DiffLexer

from django_devicectl.models import (
    Device,
    DeviceConfigHistory,
    DeviceOperationalStatus,
    DeviceRefereeReport,
    Facility,
    IPAddress,
    LogicalPort,
    MacAddress,
    PhysicalPort,
    Port,
    PortInfo,
    VirtualPort,
)


@admin.register(Facility)
class FacilityAdmin(VersionAdmin):
    list_display = ("id", "org", "name", "slug", "created", "updated")


class DeviceOperationalStatusInline(admin.TabularInline):
    model = DeviceOperationalStatus
    fields = ("status", "error_message", "pretty_diff", "event", "created", "updated")
    readonly_fields = (
        "status",
        "error_message",
        "pretty_diff",
        "event",
        "created",
        "updated",
    )
    extra = 0

    def pretty_diff(self, obj):
        if obj.diff is None:
            return "No diff"
        formatter = HtmlFormatter(style="colorful")
        highlighted_diff = highlight(obj.diff, DiffLexer(), formatter)
        css = formatter.get_style_defs(".highlight")
        return mark_safe(
            f'<div style="white-space: pre-wrap;"><style>{css}</style>{highlighted_diff}</div>'
        )

    pretty_diff.short_description = "Pretty diff"


@admin.register(Device)
class DeviceAdmin(VersionAdmin):
    list_display = ("id", "org", "name", "type", "created", "updated")
    search_fields = ("name", "instance__org__name", "instance__org__slug")
    list_filter = ("type",)
    inlines = [DeviceOperationalStatusInline]


@admin.register(DeviceOperationalStatus)
class DeviceOperationalStatusAdmin(VersionAdmin):
    list_display = ("id", "device", "status", "error_message", "created", "updated")
    list_filter = ("status",)
    search_fields = (
        "device__name",
        "device__instance__org__slug",
        "device__facility__slug",
        "error_message",
    )
    read_only_fields = ("current_config", "reference_config")


@admin.register(DeviceConfigHistory)
class DeviceConfigHistoryAdmin(VersionAdmin):
    list_display = ("id", "device", "status", "error_message", "created", "updated")
    list_filter = ("status",)
    search_fields = (
        "device__name",
        "device__instance__org__slug",
        "device__facility__slug",
        "error_message",
    )
    read_only_fields = ("current_config", "reference_config")


@admin.register(DeviceRefereeReport)
class DeviceRefereeReportAdmin(VersionAdmin):
    list_display = ("id", "org", "device", "status", "kind", "created")
    list_filter = ("kind",)
    search_fields = (
        "device__name",
        "device__instance__org__slug",
        "device__facility__slug",
        "kind",
    )
    read_only_fields = ("report", "org")


@admin.register(LogicalPort)
class LogicalPortAdmin(VersionAdmin):
    list_display = ("id", "org", "name", "trunk", "channel", "created", "updated")


@admin.register(PhysicalPort)
class PhysicalPortAdmin(VersionAdmin):
    list_display = ("id", "org", "device", "name", "logical_port", "created", "updated")


@admin.register(VirtualPort)
class VirtualPortAdmin(VersionAdmin):
    list_display = (
        "id",
        "org",
        "display_name",
        "logical_port",
        "vlan_id",
        "created",
        "updated",
    )
    search_fields = (
        "port__port_info__instance__org__name",
        "port__port_info__instance__org__slug",
        "port__port_info__ips__address",
        "name",
        "reference",
    )


@admin.register(IPAddress)
class IPAddressAdmin(VersionAdmin):
    list_display = ("id", "org", "address", "created", "updated")
    search_fields = ("address",)


@admin.register(MacAddress)
class MacAddressAdmin(VersionAdmin):
    list_display = ("id", "org", "address", "created", "updated")
    search_fields = ("address",)


@admin.register(Port)
class PortAdmin(VersionAdmin):
    list_display = (
        "id",
        "name",
        "org",
        "virtual_port",
        "port_info",
        "created",
        "updated",
        "device",
    )


class IPAddressInline(admin.TabularInline):
    model = IPAddress
    fields = ("address", "instance", "created", "updated")
    readonly_fields = ("created", "updated")
    extra = 0


class MacAddressInline(admin.TabularInline):
    model = MacAddress
    fields = ("address", "instance", "created", "updated")
    readonly_fields = ("created", "updated")
    extra = 0


@admin.register(PortInfo)
class PortInfoAdmin(VersionAdmin):
    list_display = (
        "id",
        "org",
        "device",
        "port",
        "ip_address_4",
        "ip_address_6",
        "is_management",
        "is_routeserver_peer",
        "speed",
        "created",
        "updated",
    )

    readonly_fields = ("device",)
    search_fields = ("port__virtual_port__logical_port__physical_ports__device__name",)
    inlines = [IPAddressInline, MacAddressInline]
