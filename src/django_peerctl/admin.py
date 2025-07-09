from django import forms
from django import forms as baseForms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin

from django_peerctl.models import (
    AuditLog,
    DeviceTemplate,
    EmailLog,
    EmailLogRecipient,
    InternetExchange,
    MacAddress,
    Network,
    Organization,
    PeerNetwork,
    PeerPort,
    PeerRequest,
    PeerRequestLocation,
    PeerSession,
    Policy,
    PolicyPeerGroup,
    Port,
    PortInfo,
    UserSession,
    Wish,
    ref_fallback,
)


from django_peerctl.models.tasks import RequestDummyPorts

def status_form(choices=None):
    if not choices:
        choices = [
            ("ok", "ok"),
        ]

    class StatusForm(baseForms.ModelForm):
        status = baseForms.ChoiceField(choices=choices)

    return StatusForm


class CachedPortMixin:
    def _cache_ports(self, qs):
        """
        Caches Port instances in _ports
        """

        if hasattr(self, "_ports"):
            return

        self._ports = {
            port.id: port
            for port in Port().objects(
                id__in=[i for i in qs.values_list("port", flat=True)]
            )
        }

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        self._cache_ports(qs)
        return qs


@admin.register(Network)
class NetworkAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "asn",
        "name",
        "org",
        "policy4",
        "policy6",
        "created",
        "updated",
        "email_override",
    )
    search_fields = ("asn",)
    readonly_fields = ("policy4", "policy6")
    fields = (
        "asn",
        "max_sessions",
        "status",
        "org",
        "as_set_override",
        "prefix4_override",
        "prefix6_override",
        "network_type_override",
    )
    form = status_form()


@admin.register(PeerNetwork)
class PeerNetworkAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "net",
        "peer",
        "md5_set",
        "info_prefixes4",
        "info_prefixes6",
        "created",
        "updated",
    )
    search_fields = ("net__asn", "peer__asn")

    def md5_set(self, obj):
        if obj.md5:
            return "yes"
        return "no"


@admin.register(PeerPort)
class PeerPortAdmin(admin.ModelAdmin):
    list_display = ("id", "peer_net", "port_info", "created", "updated")


class MacAddressInline(admin.TabularInline):
    model = MacAddress
    extra = 0

@admin.register(PortInfo)
class PortInfoAdmin(CachedPortMixin, admin.ModelAdmin):
    list_display = ("net", "asn", "ref_id", "ip4", "ip6", "port")
    readonly_fields = ("asn", "ix", "ip4", "ip6", "ref_ix_id")
    search_fields = ("net__asn",)
    form = status_form()
    inlines = (MacAddressInline,)

    def asn(self, obj):
        return obj.net.asn

    @ref_fallback(None)
    def ip4(self, obj):
        try:
            return self._ports.get(int(obj.port)).ip_address_4
        except (KeyError, AttributeError, TypeError):
            pass

        return obj.ip_address_4 or obj.ref.ipaddr4

    @ref_fallback(None)
    def ip6(self, obj):
        try:
            return self._ports.get(int(obj.port)).ip_address_6
        except (KeyError, AttributeError, TypeError):
            pass

        return obj.ip_address_6 or obj.ref.ipaddr6


@admin.register(DeviceTemplate)
class DeviceTemplateAdmin(admin.ModelAdmin):
    pass


@admin.register(Wish)
class WishAdmin(admin.ModelAdmin):
    list_display = ("user", "path", "text", "ticket", "status", "created")
    form = status_form()


class PeerRequestLocationInline(admin.TabularInline):
    model = PeerRequestLocation
    extra = 0


@admin.register(PeerRequest)
class PeerRequestAdmin(admin.ModelAdmin):
    search_fields = ("net__asn", "peer_asn")
    list_display = ("net", "peer_asn", "type", "status", "created", "updated")

    inlines = (PeerRequestLocationInline,)


@admin.register(PeerSession)
class PeerSessionAdmin(CachedPortMixin, admin.ModelAdmin):
    search_fields = ("peer_port__peer_net__net__asn", "peer_port__peer_net__peer__asn")
    list_display = (
        "id",
        "net",
        "peer",
        "ix_id",
        "ix_name",
        "ip4",
        "ip6",
        "peer_ipaddr4",
        "peer_ipaddr6",
        "policy4",
        "policy6",
        "status",
        "request_status",
        "created",
        "updated",
        "port",
        "device",
    )
    list_filter = ("status",)
    form = status_form(
        choices=[("ok", "ok"), ("requested", "requested"), ("configured", "configured")]
    )

    readonly_fields = ("net", "peer", "policy4", "policy6", "request_status")

    def net(self, obj):
        return obj.peer_port.peer_net.net

    def peer(self, obj):
        return obj.peer_port.peer_net.peer

    @ref_fallback(0)
    def ix_id(self, obj):
        if not obj.port:
            return None

        return self._ports.get(int(obj.port)).port_info_object.ix.id

    @ref_fallback(None)
    def ix_name(self, obj):
        if not obj.port:
            return None

        return self._ports.get(int(obj.port)).port_info_object.ix.name

    @ref_fallback(None)
    def ip4(self, obj):
        if not obj.port:
            return None

        try:
            return self._ports.get(int(obj.port)).ip_address_4
        except (KeyError, AttributeError):
            pass

        return obj.port.object.port_info_object.ipaddr4

    @ref_fallback(None)
    def ip6(self, obj):
        if not obj.port:
            return None

        try:
            return self._ports.get(int(obj.port)).ip_address_6
        except (KeyError, AttributeError):
            pass

        return obj.port.object.port_info_object.ipaddr6

    def peer_ipaddr4(self, obj):
        return obj.peer_port.port_info.ipaddr4

    def peer_ipaddr6(self, obj):
        return obj.peer_port.port_info.ipaddr6

    def request_status(self, obj):
        return obj.status


class OrganizationForm(forms.ModelForm):
    """
    Django doesn't come with a premade way to add existing
    objects as relationships, so we make a form that provides
    a field to add and remove networks for an organization
    """

    class Meta:
        model = Organization
        fields = ("name", "networks")

    # add / remove networks through filtered select widget
    networks = forms.ModelMultipleChoiceField(
        queryset=Network.objects.filter(status="ok"),
        widget=admin.widgets.FilteredSelectMultiple("Networks", is_stacked=False),
        required=False,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance:
            self.fields["networks"].initial = self.instance.net_set.all()

    def save(self, *args, **kwargs):
        instance = super().save(*args, **kwargs)
        self.fields["networks"].initial.update(org=None)
        instance.save()
        self.cleaned_data["networks"].update(org=instance)
        return instance


# XXX OLD organization admin - still need?
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "net_count", "created", "updated")
    fields = ("name", "networks")
    readonly_fields = ("net_count",)
    search_fields = ("name", "net_set__asn")
    form = OrganizationForm

    def net_count(self, obj):
        return obj.net_set.all().count()


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("net", "event", "user", "data", "created")
    readonly_fields = ("created", "updated", "version")
    form = status_form()


class EmailLogRecipientInline(admin.TabularInline):
    model = EmailLogRecipient
    fields = ("email", "asn")
    form = status_form()


@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    search_fields = ("net__asn", "sender_address", "qset_recipient__email")
    list_display = (
        "net",
        "origin",
        "user",
        "sender_address",
        "subject",
        "recipients",
        "recipient",
        "created",
    )
    inlines = (EmailLogRecipientInline,)
    readonly_fields = ("recipients", "created", "updated", "version")
    form = status_form()


@admin.register(Policy)
class PolicyAdmin(admin.ModelAdmin):
    search_fields = ("net__asn", "name")
    list_display = (
        "id",
        "net",
        "name",
        "import_policy",
        "import_policy_managed",
        "export_policy",
        "export_policy_managed",
        "peer_group",
        "peer_group_managed",
        "created",
        "updated",
    )
    form = status_form()


@admin.register(PolicyPeerGroup)
class PolicyPeerGroupAdmin(admin.ModelAdmin):
    search_fields = ("slug",)
    list_display = (
        "id",
        "net",
        "slug",
        "created",
        "updated",
    )
    autocomplete_fields = ("net",)

    form = status_form()


@admin.register(InternetExchange)
class IXAdmin(admin.ModelAdmin):
    search_fields = ("name", "name_long", "country")
    list_display = (
        "id",
        "name",
        "name_long",
        "country",
        "ref_id",
        "created",
        "updated",
    )
    form = status_form()


admin.site.unregister(get_user_model())


@admin.register(get_user_model())
class ExtendedUserAdmin(UserAdmin):
    list_display = UserAdmin.list_display + ("is_active", "last_login", "sessions")
    readonly_fields = ("sessions",)

    def sessions(self, obj):
        return UserSession.objects.filter(user=obj).count()


class RequestDummyPortsForm(forms.ModelForm):
    """
    Form for creating ``RequestDummyPorts`` tasks.

    The form adds an extra ``asn`` integer field while keeping the model's
    ``org`` ForeignKey untouched.  By relying on the standard ``autocomplete_fields``
    mechanism in the corresponding ``ModelAdmin`` we get the regular Django-admin
    autocomplete widget out of the box.
    """

    # Extra (non-model) field – single ASN to request dummy ports for.
    asn = forms.IntegerField(
        label="ASN",
        help_text="Enter a single ASN to request dummy ports for",
        min_value=1,
        max_value=4294967295,  # Max ASN value
    )

    class Meta:
        model = RequestDummyPorts
        # Only include model fields we actually want to expose.  ``org`` is kept so
        # that ``autocomplete_fields`` can inject the standard AutocompleteSelect
        # widget automatically.
        fields = ("org",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Restrict organizations to those in "ok" status.
        self.fields["org"].queryset = Organization.objects.filter(status="ok")

    def save(self, commit: bool = True):
        """Create and return a ``RequestDummyPorts`` task instance.

        Instead of persisting the bound instance coming from *ModelForm*, we
        delegate to the model's ``create_task`` class-method so that the new
        task is set up exactly the same way it would be from application code.
        """

        # Make sure the form is valid – this mirrors the behaviour of the
        # default *ModelForm.save* implementation.
        if not self.is_valid():  # pragma: no cover – admin already validates
            raise ValueError("Cannot save an invalid form.")

        org = self.cleaned_data["org"]
        asn = self.cleaned_data["asn"]

        # The task API expects a list of ASNs.
        task = RequestDummyPorts.create_task(org=org, asns=[asn])

        return task

    # The admin changeform processing pipeline calls ``form.save_m2m`` even when
    # the form has no many-to-many fields.  Provide a harmless no-op implementation
    # so that the custom save logic above does not raise an AttributeError.
    def save_m2m(self):  # pragma: no cover
        return None


@admin.register(RequestDummyPorts)
class RequestDummyPortsAdmin(admin.ModelAdmin):
    list_display = ("org", "asns", "status", "created", "updated", "error_type")
    readonly_fields = ("asns", "status", "error_type")
    form = RequestDummyPortsForm
    search_fields = ("org__name", "org__slug")

    # Use the built-in autocomplete widget for the ``org`` relation.
    autocomplete_fields = ("org",)

    # Display just the relevant fields in the form.
    fields = ("org", "asn")

    # this query set needs to filter `op` = "task_request_dummy_ports"
    def get_queryset(self, request):
        return super().get_queryset(request).filter(op="task_request_dummy_ports")

    def asns(self, obj):
        return ", ".join(str(asn) for asn in obj.param.get("kwargs", {}).get("asns", []))

    def org(self, obj):
        return obj.org

    def error_type(self, obj):
        if obj.status == "failed":
            if "ASNClaimed" in obj.error:
                return "ASN already claimed"
            return "Unhandled error"
        return None