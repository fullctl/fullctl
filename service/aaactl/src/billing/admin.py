from typing import Optional

import billing.product_handlers
from applications.service_bridge import get_client_bridge, get_client_bridge_cls
from billing.models import (
    BillingContact,
    CustomerData,
    Invoice,
    InvoiceLine,
    Ledger,
    Order,
    OrderHistory,
    OrderHistoryItem,
    OrderLine,
    OrganizationProduct,
    OrganizationProductHistory,
    Payment,
    PaymentCharge,
    PaymentMethod,
    Product,
    ProductGroup,
    ProductModifier,
    ProductPermissionGrant,
    RecurringProduct,
    Subscription,
    SubscriptionCycle,
    SubscriptionCycleCharge,
    SubscriptionCycleProduct,
    SubscriptionProduct,
    SubscriptionProductModifier,
)
from django import forms
from django.contrib import admin
from django.http import JsonResponse
from django.http.request import HttpRequest
from django.urls import path, reverse
from django.utils.html import format_html
from django.utils.translation import gettext as _

from fullctl.django.admin import BaseAdmin


# Register your models here.
class ChoiceFieldNoValidation(forms.ChoiceField):
    def validate(self, value):
        pass


class ProductForm(forms.ModelForm):
    pass


class ProductModifierInline(admin.TabularInline):
    model = ProductModifier
    fields = ("type", "value", "duration", "code")
    extra = 0


class RecurringProductInline(admin.StackedInline):
    model = RecurringProduct
    fields = (
        "type",
        "price",
        "reset_price",
        "unit",
        "unit_plural",
        "metered_url",
        "data",
    )
    extra = 0


class ProductPermissionGrantInline(admin.StackedInline):
    model = ProductPermissionGrant
    fields = ("managed_permission",)
    extra = 1


@admin.register(Product)
class ProductAdmin(BaseAdmin):
    list_display = (
        "name",
        "group",
        "component",
        "component_billable_entity",
        "description",
        "price",
        "is_recurring_product",
        "recurring_price",
        "recurring_reset_price",
        "trial_product",
    )
    search_fields = (
        "name",
        "component",
        "group",
    )
    readonly_fields = BaseAdmin.readonly_fields + (
        "is_recurring_product",
        "recurring_price",
        "recurring_reset_price",
    )
    inlines = (
        ProductModifierInline,
        RecurringProductInline,
        ProductPermissionGrantInline,
    )
    form = ProductForm

    def is_recurring_product(self, obj):
        if obj.is_recurring_product:
            return True
        return False

    def recurring_price(self, obj):
        if obj.is_recurring_product:
            return obj.recurring_product.price

    def recurring_reset_price(self, obj):
        if obj.is_recurring_product:
            return obj.recurring_product.reset_price
        return None

    recurring_reset_price.short_description = "Reset Price"
    recurring_reset_price.boolean = True


@admin.register(ProductModifier)
class ProductModifieradmin(BaseAdmin):
    list_display = ("product", "type", "value", "duration", "code")
    search_fields = ("product__name", "code")


@admin.register(OrganizationProduct)
class OrganizationProduct(BaseAdmin):
    list_display = (
        "org",
        "product",
        "subscription",
        "subscription_product",
        "component",
        "component_object",
        "created",
        "updated",
        "expires",
    )
    search_fields = ("product__name", "org__name", "org__slug")
    readonly_fields = ("component_object", "component")
    list_filter = ("product__component__slug",)
    autocomplete_fields = ("org",)

    def component_object(self, obj):
        try:
            return f"{obj.component_object_name} ({obj.component_object_id})"
        except AttributeError:
            return None

    def component(self, obj):
        try:
            return obj.product.component.slug
        except AttributeError:
            return None


@admin.register(OrganizationProductHistory)
class OrganizationProductHistoryAdmin(BaseAdmin):
    list_display = (
        "org",
        "product",
        "component_object_id",
        "component_object_name",
        "created",
        "updated",
    )
    search_fields = ("product__name", "org__name", "org__slug")
    list_filter = ("product__component__slug",)
    autocomplete_fields = ("org",)


class SubscriptionProductModifierInline(admin.TabularInline):
    model = SubscriptionProductModifier
    fields = ("type", "value", "valid", "source")
    extra = 1


class SubscriptionCycleInline(admin.TabularInline):
    model = SubscriptionCycle
    fields = ("start", "end", "status", "charge_status_link")
    readonly_fields = ("charge_status_link",)
    extra = 0

    def charge_status_link(self, obj):
        """
        This method returns a link to the admin page of the PaymentCharge object associated with the SubscriptionCycle.
        The link text is the charge status.
        """
        # Get the charge status
        charge_status = obj.charge_status

        # If there is no charge, return None
        if not charge_status:
            return None

        # Get the charge object
        charge = obj.subscription_cycle_charge_set.order_by("-created").first()

        # If there is no charge, return None
        if not charge:
            return None

        # Create the link to the admin page of the PaymentCharge object
        url = reverse(
            "admin:billing_paymentcharge_change", args=[charge.payment_charge.id]
        )

        # Return the link with the charge status as the link text
        return format_html('<a href="{}">{}</a>', url, charge_status)

    # Set short description and allow HTML
    charge_status_link.short_description = "Charge Status"
    charge_status_link.allow_tags = True

    # def has_change_permission(self, request, obj=None):
    #    return not obj.ended if obj else False

    def has_delete_permission(self, request, obj=None):
        return False


class SubscriptionProductForm(forms.ModelForm):
    component_object_id = ChoiceFieldNoValidation(choices=[])

    class Meta:
        model = SubscriptionProduct
        fields = "__all__"

    def clean_component_object_id(self):
        component_object_id = self.cleaned_data.get("component_object_id")
        if component_object_id:
            component_object_id = int(component_object_id)
        else:
            component_object_id = None
        return component_object_id


class SubscriptionProductInline(admin.TabularInline):
    model = SubscriptionProduct
    form = SubscriptionProductForm
    fields = (
        "product",
        "component",
        "component_object_id",
        "component_object_name",
        "expires",
    )
    readonly_fields = ("component", "component_object_name")
    extra = 0

    def has_change_permission(self, request, obj=None):
        # for signals to work correctly, dont allow changes to
        # existing sub - product relationships directly
        #
        # the user is forced to instead delete the existing relationship
        # and add a new one to make a change
        return False


class SubscriptionAdminForm(forms.ModelForm):
    """
    Custom form for SubscriptionAdmin to filter payment_method field
    """

    class Meta:
        model = Subscription
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        org = self.instance.org if self.instance.pk else None
        if org and self.instance.pk:
            self.fields["payment_method"].queryset = PaymentMethod.objects.filter(
                billing_contact__org=org
            )
        elif self.instance.pk:
            self.fields["payment_method"].queryset = PaymentMethod.objects.none()
        else:
            self.fields["payment_method"].queryset = PaymentMethod.objects.all()


@admin.register(Subscription)
class SubscriptionAdmin(BaseAdmin):
    list_display = (
        "group",
        "org",
        "subscription_cycle",
        "subscription_cycle_start",
        "billing_paused",
    )
    search_fields = ("group__name", "product__name", "org__name")
    list_filter = (
        "status",
        "billing_paused",
    )
    autocomplete_fields = ("org",)
    inlines = (
        SubscriptionProductInline,
        SubscriptionCycleInline,
    )
    form = SubscriptionAdminForm

    class Media:
        js = ("billing/admin.js",)  # Include the JavaScript file in Django admin

    def get_urls(self):
        urls = super().get_urls()
        my_urls = [
            path(
                "component-entities/",
                self.admin_site.admin_view(self.load_component_objects),
                name="ajax_load_component_objects",
            ),
            path(
                "payment-methods/",
                self.admin_site.admin_view(self.load_payment_methods),
                name="ajax_load_payment_methods",
            ),
        ]
        return my_urls + urls

    def load_component_objects(self, request):
        """
        This view returns a list of component objects for a given product.
        """
        product_id = request.GET.get("product_id")
        org_id = request.GET.get("org_id")
        product = Product.objects.get(id=product_id)

        bridge = get_client_bridge(
            product.component.slug, product.component_billable_entity
        )

        objects = [
            {"id": obj.id, "name": obj.name} for obj in bridge.objects(org=org_id)
        ]

        # prepend an empty option (null)

        objects.insert(0, {"id": None, "name": "---------"})

        return JsonResponse(objects, safe=False)

    def load_payment_methods(self, request):
        """
        This view returns a list of payment methods for a given org.
        """
        org_id = request.GET.get("org_id")
        payment_methods = PaymentMethod.objects.filter(billing_contact__org_id=org_id)

        methods = [{"id": method.id, "name": method.name} for method in payment_methods]
        # prepend an empty option (null)

        methods.insert(0, {"id": None, "name": "---------"})
        return JsonResponse(methods, safe=False)


class SubscriptionCycleProductInline(admin.TabularInline):
    model = SubscriptionCycleProduct
    extra = 0


class SubscriptionCycleChargeInline(admin.TabularInline):
    model = SubscriptionCycleCharge
    extra = 0
    fields = ("status", "payment_charge")
    readonly_fields = ("payment_charge",)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(SubscriptionCycle)
class SubscriptionCycleAdmin(BaseAdmin):
    list_display = (
        "subscription",
        "start",
        "end",
        "status",
        "charge_status",
        "organization_name",
    )
    search_fields = (
        "subscription__product__name",
        "subscription__org__name",
        "group__name",
        "subscription__id",
    )
    inlines = (SubscriptionCycleProductInline, SubscriptionCycleChargeInline)

    def organization_name(self, obj):
        return obj.subscription.org.name


@admin.register(SubscriptionProductModifier)
class SubscriptionProductModifierAdmin(BaseAdmin):
    list_display = ("subscription_product", "type", "value", "valid", "source")
    search_fields = (
        "subscription_product__name",
        "subscription_product__subscription__org___name",
    )


class OrderHistoryItemInline(admin.TabularInline):
    model = OrderHistoryItem
    extra = 0
    fields = ("subscription_cycle_product", "description", "price")


@admin.register(OrderHistory)
class OrderHistoryAdmin(BaseAdmin):
    list_display = ("id", "org", "billing_contact", "price", "notes", "processed")
    search_fields = ("billing_contact__name",)
    inlines = (OrderHistoryItemInline,)
    readonly_fields = ("org",)

    def org(self, obj):
        return obj.billing_contact.org


class PaymentMethodForm(forms.ModelForm):
    processor = forms.ChoiceField(
        choices=billing.payment_processors.choices(), required=True
    )


@admin.register(PaymentMethod)
class PaymentMethodAdmin(BaseAdmin):
    list_display = ("id", "name", "billing_contact", "processor", "status")
    search_fields = ("billing_contact__name",)
    form = PaymentMethodForm


@admin.register(PaymentCharge)
class PaymentChargeAdmin(BaseAdmin):
    list_display = (
        "id",
        "payment_method",
        "billing_contact",
        "price",
        "status",
        "created",
        "updated",
    )
    search_fields = (
        "payment_method__billing_contact__email",
        "payment_method__billing_contact__name",
        "payment_method__billing_contact__org__name",
        "payment_method__billing_contact__org__slug",
    )
    list_filter = ("status",)

    def billing_contact(self, obj):
        if not obj.payment_method:
            return None
        return obj.payment_method.billing_contact


@admin.register(CustomerData)
class CustomerDataAdmin(BaseAdmin):
    list_dispaly = ("id", "billing_contact")
    search_fields = ("billing_contact_name",)


@admin.register(ProductGroup)
class ProductGroupAdmin(BaseAdmin):
    list_display = ("id", "name")


@admin.register(BillingContact)
class BillingContactAdmin(BaseAdmin):
    list_display = ("id", "org", "name", "email", "created", "status")
    search_fields = ("org__name", "name", "email")
    list_filter = ("status",)
    autocomplete_fields = ("org",)


@admin.register(Ledger)
class LedgerAdmin(BaseAdmin):
    list_display = (
        "id",
        "org",
        "content_type",
        "order_number",
        "invoice_number",
        "description",
        "amount",
        "currency",
        "txn_id",
        "created",
    )
    readonly_fields = (
        "description",
        "amount",
        "currency",
        "order_number",
        "invoice_number",
        "txn_id",
    )
    search_fields = ("org__name", "org__slug", "order_number", "invoice_number")

    def org(self, obj):
        if obj.content_object:
            return obj.content_object.org

    def ref_tag(self, obj):
        if obj.content_object:
            return obj.content_object.HandleRef.tag

    def description(self, obj):
        if obj.content_object:
            return getattr(obj.content_object, "description", None)

    def txn_id(self, obj):
        if obj.content_object:
            return getattr(obj.content_object, "payment_processor_txn_id", None)

    def amount(self, obj):
        if obj.content_object:
            return obj.content_object.amount

    def currency(self, obj):
        if obj.content_object:
            return obj.content_object.currency


class OrderLineInlineAdmin(admin.TabularInline):
    model = OrderLine
    extra = 0


@admin.register(Order)
class OrderAdmin(BaseAdmin):
    list_display = (
        "order_number",
        "invoice",
        "org",
        "created",
    )

    actions = ["invoice_order"]

    autocomplete_fields = ("org",)

    inlines = (OrderLineInlineAdmin,)

    search_fields = ("org__name", "org__slug", "order_number", "invoice_number")

    def invoice_order(self, request, queryset):
        """
        Create invoices out of selected orders
        """

        for order in queryset:
            order.create_invoice()

    invoice_order.short_description = "Invoice selected orders"


class InvoiceLineInlineAdmin(admin.TabularInline):
    model = InvoiceLine
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(BaseAdmin):
    list_display = (
        "invoice_number",
        "order",
        "org",
        "status",
        "created",
    )

    autocomplete_fields = ("order", "org", "charge_object")

    inlines = (InvoiceLineInlineAdmin,)

    search_fields = ("org__name", "org__slug", "order__order_number", "invoice_number")

    readonly_fields = ("paid",)


@admin.register(Payment)
class PaymentAdmin(BaseAdmin):
    list_display = (
        "invoice_number",
        "order_number",
        "org",
        "created",
        "payment_processor_txn_id",
        "currency",
        "amount",
        "charge_object",
    )

    search_fields = (
        "org__name",
        "org__slug",
        "order_number",
        "invoice_number",
        "payment_processor_txn_id",
    )
