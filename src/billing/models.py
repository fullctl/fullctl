import datetime
import secrets
import uuid

import dateutil.relativedelta
import reversion
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.validators import EmailValidator
from django.db import models, transaction
from django.shortcuts import render
from django.utils import timezone
from django.utils.translation import gettext as _
from django_countries.fields import CountryField
from django_grainy.decorators import grainy_model
from fullctl.django.fields.service_bridge import ReferencedObjectField
from fullctl.django.models.concrete import AuditLog
from phonenumber_field.modelfields import PhoneNumberField

import account.models
import applications.models
import billing.const as const
import billing.payment_processors
import billing.product_handlers
from applications.service_bridge import get_client_bridge, get_client_bridge_cls
from billing.exceptions import OrgProductAlreadyExists
from common.email import email
from common.models import HandleRefModel

# Create your models here.


@reversion.register()
class ProductGroup(HandleRefModel):

    """
    Describes a container for a set of products (cyclic or one-time purchases)

    This allows the grouping of products for billing purposes, which can be useful if you want.

    An example here would be "Fullctl" as a product group for all it's underlying
    products/services (ixctl, prefixctl etc.)
    """

    name = models.CharField(max_length=255)
    subscription_cycle_anchor = models.DateField(
        null=True,
        blank=True,
        help_text=_(
            "If specified, sets a day of the month to be used as the anchor point for subscription subscription_cycles"
        ),
    )

    class HandleRef:
        tag = "product_group"

    class Meta:
        db_table = "billing_product_group"
        verbose_name = _("Product Group")
        verbose_name_plural = _("Product Groups")

    def __str__(self):
        return self.name


@reversion.register()
class Product(HandleRefModel):

    """
    Describes a product or service.
    """

    # example: fullctl.prefixctl.prefixes
    name = models.CharField(
        max_length=255, help_text=_("Internal product name"), unique=True
    )

    component = models.ForeignKey(
        applications.models.Service,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products",
        help_text=_("Product belongs to component"),
    )

    component_billable_entity = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        verbose_name=_("Billed object"),
        help_text=_(
            "Links the product to specific entity type in the component (.e.g, InternetExchange for ixctl). Free-form field at this point. Ask developers if you are unsure."
        ),
    )

    # example: actively monitored prefixes
    description = models.CharField(
        max_length=255,
        help_text=_("Description of the product or service being billed"),
    )

    group = models.ForeignKey(
        ProductGroup,
        related_name="product_set",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text=_("Allows you to group products together for billing purposes"),
    )

    price = models.DecimalField(
        default=0.00,
        max_digits=8,
        decimal_places=2,
        help_text=_(
            "Price charge on initial setup / purchase. For recurring_product pricing this could specify a setup fee. For non-recurring_product pricing, this is the product price."
        ),
    )

    data = models.JSONField(
        help_text=_("Arbitrary extra data you want to define for this product"),
        blank=True,
        default=dict,
    )

    expiry_period = models.PositiveIntegerField(
        default=0,
        help_text=_("Product expires after N days"),
    )

    expiry_replacement_product = models.ForeignKey(
        "billing.Product",
        null=True,
        blank=True,
        related_name="expiry_replacement_for",
        on_delete=models.SET_NULL,
        help_text=_(
            "On products that can expire, replace the expired product with this product"
        ),
    )

    trial_product = models.ForeignKey(
        "billing.Product",
        null=True,
        blank=True,
        related_name="trial_of",
        on_delete=models.SET_NULL,
        help_text=_(
            "This product's trial version",
        ),
    )

    renewable = models.IntegerField(
        default=0,
        help_text=_(
            "Product can be renewed N days after it expired. 0 for instantly, -1 for never."
        ),
    )

    class HandleRef:
        tag = "product"

    class Meta:
        db_table = "billing_product"
        verbose_name = _("Product")
        verbose_name_plural = _("Products")
        ordering = ["name"]

    @property
    def is_recurring_product(self):
        return hasattr(self, "recurring_product") and bool(self.recurring_product.id)

    def __str__(self):
        return f"{self.name}: {self.description}"

    def create_transactions(self, org):
        order_number = unique_order_id()
        self._create_order(org, order_number)

        invoice_number = unique_invoice_id()
        self._create_invoice(org, invoice_number, order_number)
        self._create_payment(org, invoice_number)

    def _create_order(self, org, order_number):
        order, _ = Order.objects.get_or_create(
            org=org,
            order_number=order_number,
        )

        order_line = OrderLine.objects.create(
            amount=self.price, product=self, description=self.description, order=order
        )
        return order_line

    def _create_invoice(self, org, invoice_number, order_number):
        invoice, _ = Invoice.objects.get_or_create(
            org=org,
            invoice_number=invoice_number,
            order=Order.objects.get(order_number=order_number),
        )

        invoice_line = InvoiceLine.objects.create(
            # Not sure how we want to access this
            amount=self.price,
            product=self,
            description=self.description,
            invoice=invoice,
        )
        return invoice_line

    def _create_payment(self, org, invoice_number):
        payment = Payment.objects.create(
            org=org,
            amount=self.price,
            # billing_contact=None,
            # payment_method=None,
            invoice_number=invoice_number,
        )
        return payment

    def can_add_to_org(self, org, component_object_id=None):
        """
        Checks whether or not this product can be added to the supplied org.
        """

        if self.component_billable_entity and not component_object_id:
            # product requires a component_object_id but none was supplied

            return False

        if not self.component_billable_entity and component_object_id:
            # product does not require a component_object_id but one was supplied
            return False

        org_product = org.products.filter(
            product=self, component_object_id=component_object_id
        )

        if org_product.exists():
            return False

        # if product is trial of another product and org as the `real` product
        # then we can't add the trial product

        for trial_product in self.trial_of.all():
            for org_product in org.products.filter(product=trial_product):
                if org_product.component_object_id == component_object_id:
                    return False

        most_recent = (
            OrganizationProductHistory.objects.filter(
                org=org, product=self, component_object_id=component_object_id
            )
            .order_by("-created")
            .first()
        )

        if not most_recent:
            return True

        if self.renewable == 0:
            return True

        if self.renewable == -1:
            return False

        tdiff = (timezone.now() - most_recent.created).total_seconds() / 86400

        return tdiff > self.renewable

    def add_to_org(self, org, notes=None, component_object_id=None):
        """
        Attempts to add this product to the supplied org.

        Raises OrgProductAlreadyExists if the product already exists on the org with
        the same component_object_id.
        """

        qset = org.products.filter(
            product=self, component_object_id=component_object_id
        )

        if qset.exists():
            raise OrgProductAlreadyExists(f"{org.slug} - {self}")

        if self.expiry_period:
            expires = timezone.now() + datetime.timedelta(days=self.expiry_period)
        else:
            expires = None

        # non recurring products can be added standalone
        if not self.is_recurring_product:
            OrganizationProduct.objects.create(
                org=org,
                product=self,
                notes=notes,
                expires=expires,
                component_object_id=component_object_id,
            )

        # recurring products should be added to subscription
        # if no subscription exists, create one
        subscription = org.subscription_set.filter(group=self.group).first()
        if not subscription:
            subscription = Subscription.objects.create(
                group=self.group,
                org=org,
                subscription_cycle_start=timezone.now(),
                data={"created-through": str(self), "notes": notes},
            )
        subscription_product = SubscriptionProduct(
            subscription=subscription,
            product=self,
            component_object_id=component_object_id,
            data={"notes": notes},
        )
        subscription_product.full_clean()
        subscription_product.save()

    def clean(self):
        try:
            if self.component_billable_entity:
                get_client_bridge_cls(
                    self.component.slug, self.component_billable_entity
                )
        except AttributeError as e:
            raise ValidationError(
                f"Invalid component-billable-entity for {self.component.slug}: {e}"
            )


@reversion.register()
class ProductPermissionGrant(HandleRefModel):
    """
    Describes what permissions are granted by the product when owned or activated
    by an organization.

    A product can have multiple permission grants
    """

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="managed_permissions"
    )

    managed_permission = models.ForeignKey(
        account.models.ManagedPermission,
        on_delete=models.CASCADE,
        related_name="products",
    )

    class HandleRef:
        tag = "product_permission_grant"

    class Meta:
        db_table = "billing_product_permission_grant"
        verbose_name = _("Product permission grant")
        verbose_name_plural = _("Product permission grants")

    def apply(self, org_product):
        """
        Takes and OrganizationProduct instance and ensures that the required
        OrganizationManagedPermission entries exist.
        """

        org = org_product.org

        if org.org_managed_permission_set.filter(
            product__product=self.product,
            managed_permission=self.managed_permission,
        ).exists():
            return

        account.models.OrganizationManagedPermission.objects.create(
            org=org,
            managed_permission=self.managed_permission,
            product=org_product,
            reason="product grant",
        )


@reversion.register()
class RecurringProduct(HandleRefModel):

    """
    Describes a product that can be subscribed to

    Currently supports metered or fixed pricing.
    """

    # product information
    product = models.OneToOneField(
        Product, on_delete=models.CASCADE, related_name="recurring_product"
    )

    # metered or fixed
    type = models.CharField(
        max_length=255,
        choices=const.BILLING_PRODUCT_RECURRING_TYPES,
        default=None,
        null=True,
    )

    price = models.DecimalField(
        default=0.00,
        max_digits=8,
        decimal_places=2,
        help_text=_(
            "Price for recurring product charges. For fixed pricing this is the total price charged each subscription cycle. For metered unit this would be the usage price per unit."
        ),
    )

    unit = models.CharField(
        max_length=32,
        default="Unit",
        help_text=_("Label for a unit in the context of metered usage"),
    )

    unit_plural = models.CharField(
        max_length=40,
        default="Units",
        help_text=_("Label for multiple units in the context of metered usage"),
    )

    metered_url = models.URLField(
        null=True,
        blank=True,
        help_text=_(
            "For metered charges, specify the url that is used to retrieve the current metered value"
        ),
    )

    data = models.JSONField(
        help_text=_(
            "Arbitrary extra data you want to define for this recurring_product product"
        ),
        blank=True,
        default=dict,
    )

    class Meta:
        db_table = "billing_recurring_product"
        verbose_name = _("Recurring Product Settings")
        verbose_name_plural = _("Recurring Product Settings")
        # FIXME: why is this weird on postgres
        # unique_together = ["product", "subscription_cycle"]

    class HandleRef:
        tag = "recurring_product"

    @property
    def name(self):
        return f"{self.product.name}.recurring_product"

    @property
    def type_description(self):
        if self.type == "metered":
            return _("Metered Usage")
        elif self.type == "fixed":
            return _("Fixed Price")
        else:
            return _("Subscription")

    def __str__(self):
        return f"{self.name}({self.id})"


@reversion.register()
class ProductModifier(HandleRefModel):

    """
    Describes a price modification template for a product

    It will be used to apply a price modification to a subscription
    of the same product
    """

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="modifier_set"
    )
    type = models.CharField(max_length=255, choices=const.BILLING_MODIFIER_TYPES)
    value = models.PositiveIntegerField(default=0)
    duration = models.IntegerField(default=0, help_text=_("Duration in days"))
    code = models.CharField(
        max_length=255, null=True, blank=True, help_text=_("activation code")
    )

    class HandleRef:
        tag = "product_modified"

    class Meta:
        db_table = "billing_product_modifier"
        verbose_name = _("Product Price Modifier")
        verbose_name_plural = _("Product Price Modifiers")


@reversion.register()
@grainy_model("billing.services", realted="org")
class Subscription(HandleRefModel):

    """
    Describes an organization's subscription to a product group
    """

    org = models.ForeignKey(
        account.models.Organization,
        on_delete=models.CASCADE,
        related_name="subscription_set",
    )

    group = models.ForeignKey(
        ProductGroup, related_name="subscription_set", on_delete=models.CASCADE
    )

    subscription_cycle_interval = models.CharField(
        max_length=255, choices=const.BILLING_CYCLE_CHOICES, default="month"
    )
    subscription_cycle_start = models.DateTimeField(
        help_text=_("Start of billing subscription_cycle"), blank=True, null=True
    )
    subscription_cycle_frequency = models.PositiveIntegerField(default=1)

    payment_method = models.ForeignKey(
        "billing.PaymentMethod",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subscription_set",
        help_text=_("User payment option that will be charged by this subscription"),
    )

    data = models.JSONField(
        default=dict, blank=True, help_text=_("Any extra data for the subscription")
    )

    billing_paused = models.BooleanField(
        default=False,
        help_text=_("Whether billing is paused for this subscription. Cycles will still be processed but no charges will be made."),
    )

    class HandleRef:
        tag = "subscription"

    class Meta:
        db_table = "billing_subscription"
        verbose_name = _("Subscription")
        verbose_name_plural = _("Subscriptions")

    @classmethod
    def get_or_create(cls, org, group, subscription_cycle="month"):
        subscription, created_subscription = cls.objects.get_or_create(
            org=org, group=group, subscription_cycle_interval=subscription_cycle
        )

        return subscription

    @classmethod
    def set_payment_method(cls, org, payment_method=None, replace=None):
        if not payment_method:
            payment_method = PaymentMethod.get_for_org(org).first()

        qset = org.subscription_set
        if replace:
            qset = qset.filter(payment_method=replace)

        if payment_method:
            qset.update(payment_method=payment_method)

    @property
    def subscription_cycle(self):
        return self.get_subscription_cycle(datetime.date.today())

    @property
    def charge_description(self):
        return f"{self.group.name} Service Charges"

    @property
    def charge_type(self):
        """
        if there is a metered product in the subscription
        the charge type is `end` meaning, charges will
        process at the end of the cycle

        otherwise the charge type will be `start`, charges
        will process at the beginniung of the cyle
        """

        if self.subscription_product_set.filter(
            product__recurring_product__type="metered"
        ).exists():
            return "end"
        return "start"

    def __str__(self):
        return f"{self.group.name} : {self.org}"

    def get_subscription_cycle(self, date):
        return self.subscription_cycle_set.filter(start__lte=date, end__gt=date).first()

    @reversion.create_revision()
    def add_product(self, product):
        subscription_product, _ = SubscriptionProduct.objects.get_or_create(
            subscription=self, product=product
        )
        return subscription_product

    @reversion.create_revision()
    def end_subscription_cycle(self):
        """
        end current subscription subscription_cycle prematurely
        """

        if not self.subscription_cycle:
            return
        self.subscription_cycle.end = datetime.date.today()
        self.subscription_cycle.save()
        self.subscription_cycle.charge()
        self.start_subscription_cycle()

    def start_subscription_cycle(self, start=None, force=False):
        if not start:
            start = datetime.date.today()

        subscription_cycle_anchor = self.group.subscription_cycle_anchor

        if self.subscription_cycle_interval == "month":
            if subscription_cycle_anchor:
                start = start.replace(day=subscription_cycle_anchor.day)
            end = start + dateutil.relativedelta.relativedelta(months=1)

        elif self.subscription_cycle_interval == "year":
            end = start + dateutil.relativedelta.relativedelta(years=1)

        if self.subscription_cycle:
            if not force:
                raise OSError(
                    _(
                        "Currently have an active subscription_cycle, pass `force` = True to end and start a new one"
                    )
                )
            else:
                self.end_subscription_cycle()

        # delete any subscription products that end at the end of the cycle
        for subprod in self.subscription_product_set.filter(ends_next_cycle=True):
            subprod.delete()

        if not self.subscription_cycle_start:
            self.subscription_cycle_start = start
            self.save()

        subscription_cycle = SubscriptionCycle.objects.create(
            subscription=self, start=start, end=end
        )

        for subscription_product in self.subscription_product_set.all():
            SubscriptionCycleProduct.objects.create(
                subscription_cycle=subscription_cycle,
                subscription_product=subscription_product,
            )

        return subscription_cycle


@reversion.register()
class SubscriptionProduct(HandleRefModel):

    """
    Links a product to a subscription
    """

    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="subscription_product_set"
    )

    product = models.ForeignKey(
        Product, on_delete=models.CASCADE, related_name="subscription_set"
    )

    data = models.JSONField(
        default=dict,
        blank=True,
        help_text=_("Any extra data for the subscription item"),
    )

    expires = models.DateTimeField(
        blank=True,
        null=True,
        help_text=_(
            "If set, this subscription product will end and be removed at the given time"
        ),
    )

    ends_next_cycle = models.BooleanField(
        default=False,
        help_text=_(
            "If true, this subscription product will end and be removed at the end of the current subscription cycle"
        ),
    )

    component_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("ID of the component object (e.g., Internet exchange id in ixctl)"),
    )
    component_object_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        editable=False,
        help_text=_(
            "Name of the component object (e.g., Internet exchange name in ixctl) - set automatically during save"
        ),
    )

    class HandleRef:
        tag = "subscription_product"

    class Meta:
        db_table = "billing_subscription_product"
        verbose_name = _("Subscription Product")
        verbose_name_plural = _("Subscription Products")

    @property
    def component(self):
        return self.product.component

    @property
    def component_object_handle(self):
        if self.component_object_id and self.product.component_billable_entity:
            return ".".join(
                [
                    self.product.component.slug,
                    self.product.component_billable_entity,
                    str(self.component_object_id),
                ]
            )

    @property
    def component_object(self):
        if hasattr(self, "_component_object"):
            return self._component_object

        if not self.product.component:
            return None

        if not self.component_object_id:
            return None

        if not self.product.component_billable_entity:
            return None

        bridge = get_client_bridge(
            self.product.component.slug, self.product.component_billable_entity
        )

        self._component_object = bridge.first(
            id=self.component_object_id, org_slug=self.subscription.org.slug
        )
        return self._component_object

    @property
    def subscription_cycle_cost(self):
        subscription_cycle = self.subscription.subscription_cycle
        if not subscription_cycle:
            return 0
        try:
            subscription_cycle_product = (
                subscription_cycle.subscription_cycle_product_set.get(
                    subscription_product=self
                )
            )
            return subscription_cycle_product.price
        except SubscriptionCycleProduct.DoesNotExist:
            return 0

    @property
    def subscription_cycle_usage(self):
        subscription_cycle = self.subscription.subscription_cycle
        if not subscription_cycle:
            return 0
        try:
            subscription_cycle_product = (
                subscription_cycle.subscription_cycle_product_set.get(
                    subscription_product=self
                )
            )
            return subscription_cycle_product.usage
        except SubscriptionCycleProduct.DoesNotExist:
            return 0

    @property
    def description(self):
        if self.component_object_name:
            return f"{self.component_object_name} - {self.product.description}"
        return self.product.description

    def __str__(self):
        return f"{self.subscription} - {self.description}"

    def update_expires(self):
        """
        Will update the expire date of the subscription product based on the product's
        expiry date.
        """
        if not self.expires and self.product.expiry_period:
            self.expires = timezone.now() + datetime.timedelta(
                days=self.product.expiry_period
            )
            self.save()

    def clean(self):
        if self.component_object_id:
            obj = self.component_object

            if not obj:
                raise ValidationError(
                    _(f"{self.component_object_handle} does not exist")
                )

            org = account.models.Organization.objects.filter(id=obj.org_id).first()

            if not org:
                raise ValidationError(
                    _(
                        f"{self.component_object_handle} organization does not exist (reach out to devops)"
                    )
                )

            if org != self.subscription.org:
                raise ValidationError(
                    _(
                        f"{self.component_object_handle}: {obj.name}'s organization `{org.name} ({org.slug})` does not match subscription organization `{self.subscription.org.name} ({self.subscription.org.slug})`"
                    )
                )

            org_name = org.name if org else "Unknown Organization"
            self.component_object_name = f"{self.component_object.name} ({org_name})"


@reversion.register()
class SubscriptionCycle(HandleRefModel):

    """
    Describes a billing subscription_cycle for a subscription with a specified
    start and end date.

    Once the end date is reached, the subscription_cycle will be billed.
    """

    subscription = models.ForeignKey(
        Subscription, on_delete=models.CASCADE, related_name="subscription_cycle_set"
    )

    status = models.CharField(
        max_length=32,
        choices=(
            ("open", "Open"),
            ("paid", "Paid"),
            ("failed", "Payment failure"),
            ("error", "Critical error (Manually review)"),
        ),
        default="open",
    )

    error_information = models.TextField(
        blank=True, null=True, help_text=_("Error information")
    )

    start = models.DateField()
    end = models.DateField()

    class Meta:
        db_table = "billing_subscription_cycle"
        verbose_name = _("Subscription Cycle")
        verbose_name_plural = _("Subscription Cycles")

    class HandleRef:
        tag = "subscription_cycle"

    @property
    def price(self):
        """
        The current total of the subscription_cycle
        """

        price = 0
        for charge in self.subscription_cycle_product_set.all():
            price += float(charge.price)
        return price

    @property
    def ended(self):
        """
        Has this subscription_cycle ended?
        """

        if not self.end:
            return False

        return self.end <= datetime.date.today()

    @property
    def charged(self):
        """
        Has this subscription_cycle been charged already ?
        """

        return self.subscription_cycle_charge_set.filter(
            payment_charge__status="ok"
        ).exists()

    @property
    def charge_status(self):
        """
        The status of the subscription_cycle charge
        """

        charge = self.subscription_cycle_charge_set.order_by("-created").first()

        if not charge:
            if self.ended:
                return "Overdue"
            return None

        status = charge.payment_charge.status

        if status == "ok":
            return "paid"

        return status

    def __str__(self):
        return f"{self.subscription} {self.start} - {self.end}"

    def set_error(self, error):
        self.status = "error"
        self.error_information = error
        self.save()

    def update_usage(self, subscription_product, usage):
        """
        Set the usage for a subscription product in this subscription_cycle
        """

        (
            subscription_cycle_product,
            created,
        ) = SubscriptionCycleProduct.objects.get_or_create(
            subscription_cycle=self,
            subscription_product=subscription_product,
        )

        if usage is not None:
            subscription_cycle_product.usage = usage
        subscription_cycle_product.save()

    def add_subscription_product(self, subscription_product):
        """
        Add a subscription product to this subscription_cycle
        """

        SubscriptionCycleProduct.objects.get_or_create(
            subscription_cycle=self,
            subscription_product=subscription_product,
        )

    def charge(self, commit=True):
        """
        Charge the cost of the subscription_cycle to the customer's payment method
        """

        if self.charged:
            raise OSError("Cycle was already charged successfully")

        self.status = "paid"
        self.save()

        if not self.price:
            return

        pending_payment_charge = self.subscription_cycle_charge_set.filter(
            payment_charge__status="pending"
        ).first()
        if pending_payment_charge:
            return pending_payment_charge

        payment_charge = PaymentCharge.objects.create(
            payment_method=self.subscription.payment_method,
            price=self.price,
            description=self.subscription.charge_description,
        )

        subscription_cycle_charge = SubscriptionCycleCharge.objects.create(
            subscription_cycle=self, payment_charge=payment_charge, status="pending"
        )

        order_number = self.create_orders()
        invoice = self.create_invoice(order_number)

        if commit:
            self.subscription.payment_method.processor_instance.charge(payment_charge)

        payment_charge.refresh_from_db()
        if payment_charge.status == "failed":
            self.status = "failed"
            payment_charge.notify_failure()
            self.save()

        invoice.charge_object = payment_charge
        invoice.save()

        return subscription_cycle_charge

    def create_invoice(self, order_number):
        org = self.subscription.org
        invoice_number = unique_invoice_id()
        return self._create_invoices(org, invoice_number, order_number)

    def create_orders(self):
        org = self.subscription.org
        order_number = unique_order_id()
        self._create_orders(org, order_number)
        return order_number

    def create_transactions(self, org):
        # DEPRECATED
        order_number = unique_order_id()
        self._create_orders(org, order_number)

        invoice_number = unique_invoice_id()
        self._create_invoices(org, invoice_number, order_number)

    def _create_orders(self, org, order_number):
        order, _ = Order.objects.get_or_create(
            org=org,
            order_number=order_number,
        )

        for cycle_product in self.subscription_cycle_product_set.all():
            OrderLine.objects.create(
                amount=cycle_product.price,
                subscription=self.subscription,
                subscription_cycle_product=cycle_product,
                product=cycle_product.subscription_product.product,
                description=cycle_product.subscription_product.description,
                order=order,
            )

    def _create_invoices(self, org, invoice_number, order_number):
        invoice, _ = Invoice.objects.get_or_create(
            org=org,
            invoice_number=invoice_number,
            order=Order.objects.get(order_number=order_number),
        )

        for cycle_product in self.subscription_cycle_product_set.all():
            InvoiceLine.objects.create(
                amount=cycle_product.price,
                subscription=self.subscription,
                subscription_cycle_product=cycle_product,
                product=cycle_product.subscription_product.product,
                description=cycle_product.subscription_product.description,
                invoice=invoice,
            )
        return invoice


@reversion.register()
class SubscriptionCycleCharge(HandleRefModel):

    """
    Describes a billing charge made for a subscription subscription_cycle
    """

    subscription_cycle = models.ForeignKey(
        SubscriptionCycle,
        on_delete=models.CASCADE,
        related_name="subscription_cycle_charge_set",
    )
    payment_charge = models.OneToOneField(
        "billing.PaymentCharge",
        on_delete=models.CASCADE,
        related_name="subscription_cycle_charge",
    )

    class Meta:
        db_table = "billing_subscription_cycle_charge"
        verbose_name = _("Subscription Cycle Charge")
        verbose_name_plural = _("Subscription Cycle Charges")

    class HandleRef:
        tag = "subscription_cycle_charge"

    @property
    def invoice_number(self):
        return (
            self.subscription_cycle.subscription_cycle_product_set.first().invoice_number
        )


@reversion.register()
class SubscriptionCycleProduct(HandleRefModel):

    """
    Describes a relationship of a product to a subscription subscription_cycle, letting us
    specify the product's usage for the subscription_cycle.
    """

    subscription_cycle = models.ForeignKey(
        SubscriptionCycle,
        on_delete=models.CASCADE,
        related_name="subscription_cycle_product_set",
    )
    subscription_product = models.ForeignKey(
        SubscriptionProduct,
        on_delete=models.CASCADE,
        related_name="subscription_cycle_product_set",
    )
    usage = models.PositiveIntegerField(
        default=0,
        help_text=_("Usage attributed to subscription_cycle for this product"),
    )

    class Meta:
        db_table = "billing_subscription_cycle_product"
        verbose_name = _("Subscription Cycle Product")
        verbose_name_plural = _("Subscription Cycle Product")

    class HandleRef:
        tag = "subscription_cycle_product"

    @property
    def price(self):
        """
        price of the product in the subscription subscription_cycle
        """
        try:
            recurring_product = self.subscription_product.product.recurring_product
        except RecurringProduct.DoesNotExist:
            return 0

        if recurring_product.type == "metered":
            price = float(self.usage) * float(recurring_product.price)
        else:
            price = recurring_product.price

        # apply modifiers

        for mod in self.subscription_product.modifier_set.all():
            if mod.is_valid:
                price = mod.apply(price, recurring_product.price)

        return price

    @property
    def invoice_number(self):
        return self.invoice_set.first().invoice_number

    def __str__(self):
        return f"{self.subscription_product}"


@reversion.register()
class SubscriptionProductModifier(HandleRefModel):

    """
    Describes a modification for a specific product in a subscription, allowing
    us to make certain products in a subscription reduced in price or free
    entirely.
    """

    subscription_product = models.ForeignKey(
        SubscriptionProduct, on_delete=models.CASCADE, related_name="modifier_set"
    )
    type = models.CharField(max_length=255, choices=const.BILLING_MODIFIER_TYPES)
    value = models.IntegerField(default=0)
    valid = models.DateTimeField(help_text=_("Valid until"))
    source = models.CharField(
        max_length=255, help_text=_("source of modifier, why was it applied")
    )

    class HandleRef:
        tag = "subscription_product_modifier"

    class Meta:
        db_table = "billing_subscription_modifier"
        verbose_name = _("Subscription Price Modifier")
        verbose_name_plural = _("Subscription Price Modifiers")

    @property
    def is_valid(self):
        return timezone.now() < self.valid

    def apply(self, price, unit_price=0):
        """
        applies modifier to a given price and returns the modified
        price
        """
        if self.type == "free":
            return 0

        if self.type == "quantity":
            price -= float(unit_price * self.value)
        elif self.type == "reduction":
            price -= self.value
        elif self.type == "reduction_p":
            price -= price * (self.value / 100.0)

        return max(price, 0)


@reversion.register()
class OrganizationProduct(HandleRefModel):
    """
    Describes organization access to a product
    """

    org = models.ForeignKey(
        account.models.Organization,
        on_delete=models.CASCADE,
        related_name="products",
        help_text=_("Products the organization has access to"),
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="organizations",
        help_text=_("Organizations that have access to this product"),
    )

    subscription_product = models.OneToOneField(
        SubscriptionProduct,
        on_delete=models.CASCADE,
        related_name="organization_product",
        null=True,
        blank=True,
        help_text=_("Product access is granted through this subscription product"),
    )

    subscription = models.ForeignKey(
        Subscription,
        on_delete=models.CASCADE,
        related_name="applied_product_ownership",
        null=True,
        blank=True,
        help_text=_("Product access is granted through this subscription"),
    )

    component_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("ID of the component object (e.g., Internet exchange id in ixctl)"),
    )
    component_object_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        editable=False,
        help_text=_(
            "Name of the component object (e.g., Internet exchange name in ixctl) - set automatically during save"
        ),
    )

    expires = models.DateTimeField(
        help_text=_("Product access expires at this date"),
        null=True,
        blank=True,
    )

    notes = models.TextField(
        help_text=_(
            "Custom notes for why produt access was granted. Useful when access is granted manually"
        ),
        null=True,
        blank=True,
    )

    class HandleRef:
        tag = "org_product"

    class Meta:
        db_table = "billing_org_product"
        verbose_name = _("Organization Product Access")
        verbose_name_plural = _("Organization Product Access")

    @property
    def expired(self):
        if not self.expires:
            return False

        return timezone.now() >= self.expires

    def add_to_history(self):
        OrganizationProductHistory.objects.create(
            org=self.org,
            product=self.product,
            notes=self.notes,
            component_object_id=self.component_object_id,
            component_object_name=self.component_object_name,
        )


class OrganizationProductHistory(HandleRefModel):

    """
    Describes a history of organization product access
    """

    org = models.ForeignKey(
        account.models.Organization,
        on_delete=models.CASCADE,
        related_name="product_history",
        help_text=_("Products the organization has access to"),
    )

    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="organization_history",
        help_text=_("Organizations that have access to this product"),
    )

    notes = models.TextField(
        help_text=_(
            "Custom notes for why produt access was granted. Useful when access is granted manually"
        ),
        null=True,
        blank=True,
    )

    component_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text=_("ID of the component object (e.g., Internet exchange id in ixctl)"),
    )
    component_object_name = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        editable=False,
        help_text=_(
            "Name of the component object (e.g., Internet exchange name in ixctl) - set automatically during save"
        ),
    )

    class HandleRef:
        tag = "org_product_history"

    class Meta:
        db_table = "billing_org_product_history"
        verbose_name = _("Organization Product Access History")
        verbose_name_plural = _("Organization Product Access History")


def unique_id(Model, field, prefix=""):
    i = 0
    while i < 1000:
        unique_id = f"{secrets.token_urlsafe(10)}"

        if not Model.objects.filter(**{field: f"{prefix}{unique_id}"}).exists():
            return unique_id
        i += 1
    raise OSError(f"Could not generate a unique {Model} id")


def unique_order_history_id():
    return unique_id(OrderHistory, "order_id")


def unique_order_id():
    return unique_id(Order, "order_number")


def unique_invoice_id():
    return unique_id(Invoice, "invoice_number")


@reversion.register()
class OrderHistory(HandleRefModel):

    """
    Describes processed orders
    """

    billing_contact = models.ForeignKey(
        "billing.BillingContact",
        on_delete=models.SET_NULL,
        null=True,
        related_name="order_set",
    )

    payment_charge = models.OneToOneField(
        "billing.PaymentCharge",
        on_delete=models.SET_NULL,
        related_name="order",
        null=True,
    )

    billed_to = models.CharField(
        max_length=255,
        help_text=_(
            "Holds the name of the payment method that was billled for archiving purposes."
        ),
    )

    notes = models.CharField(
        max_length=255, null=True, blank=True, help_text=_("Order specific notes")
    )

    processed = models.DateTimeField(help_text=("When was this order processed"))

    order_id = models.CharField(
        max_length=16, default=unique_order_history_id, unique=True
    )

    class HandleRef:
        tag = "order_history"

    class Meta:
        db_table = "billing_order_history"
        verbose_name = _("Order History Entry")
        verbose_name_plural = _("Order History Entries")

    @classmethod
    def create_from_payment_charge(cls, payment_charge):
        order = cls(
            payment_charge=payment_charge,
            billing_contact=payment_charge.payment_method.billing_contact,
            billed_to=payment_charge.payment_method.name,
            processed=datetime.datetime.now(),
            order_id=unique_order_history_id(),
        )
        order.save()

        for order_line in payment_charge.invoice.order.order_line_set.all():
            OrderHistoryItem.objects.create(
                order=order,
                description=order_line.description,
                price=order_line.amount,
            )

        return order

    @property
    def price(self):
        price = 0
        for order_history_item in self.order_history_item_set.all():
            price += order_history_item.price
        return price

    @property
    def description(self):
        return self.payment_charge.description

    @property
    def organization_name(self):
        try:
            return (
                self.payment_charge.subscription_cycle_charge.subscription_cycle.subscription.org.name
            )
        except SubscriptionCycleCharge.DoesNotExist:
            return "-"


@reversion.register()
class OrderHistoryItem(HandleRefModel):
    order = models.ForeignKey(
        OrderHistory, on_delete=models.CASCADE, related_name="order_history_item_set"
    )

    subscription_cycle_product = models.OneToOneField(
        SubscriptionCycleProduct,
        on_delete=models.SET_NULL,
        related_name="order_history_item",
        null=True,
        blank=True,
    )

    description = models.CharField(max_length=255)

    price = models.DecimalField(
        default=0.0, max_digits=8, decimal_places=2, help_text=_("Price charged")
    )

    class HandleRef:
        tag = "order_history_item"

    class Meta:
        db_table = "billing_order_history_item"
        verbose_name = _("Order History Item")
        verbose_name_plural = _("Order History Items")


@reversion.register()
class CustomerData(HandleRefModel):
    billing_contact = models.OneToOneField(
        "billing.BillingContact", on_delete=models.CASCADE, related_name="customer"
    )
    data = models.JSONField(default=dict, blank=True)

    class HandleRef:
        tag = "customer"

    class Meta:
        db_table = "billing_customer_data"
        verbose_name = _("Customer Data")
        verbose_name_plural = _("Customer Data")

    def __str__(self):
        return f"{self.billing_contact.name} <{self.billing_contact.email}> ({self.id})"


@reversion.register()
@grainy_model("billing.contact", related="org")
class BillingContact(HandleRefModel):
    org = models.ForeignKey(
        account.models.Organization,
        on_delete=models.CASCADE,
        related_name="billing_contact_set",
    )

    name = models.CharField(max_length=255)
    email = models.EmailField(
        max_length=255,
        null=True,
        blank=True,
        validators=[
            EmailValidator(allowlist=[])
        ],  # using allowlist to match stripe valid emails
    )
    phone_number = PhoneNumberField(null=True)

    status = models.CharField(
        max_length=32,
        choices=(
            ("ok", "Ok"),
            ("deleted", "Deleted"),
        ),
        default="ok",
    )

    class Meta:
        db_table = "billing_contact"
        verbose_name = _("Billing Contact")
        verbose_name_plural = _("Billing Contacts")

    class HandleRef:
        tag = "billing_contact"

    @property
    def active(self):
        for payment_method in self.payment_method_set.filter(status="ok"):
            if payment_method.subscription_set.filter(status="ok").exists():
                return True
        return False

    def __str__(self):
        return self.name

    def notify(self, subject, message):
        if self.email:
            email(
                settings.SUPPORT_EMAIL,
                [self.email],
                subject,
                message,
            )

    def delete(self):
        try:
            super().delete()
        except models.ProtectedError:
            self.status = "deleted"
            self.save()


@reversion.register()
class PaymentMethod(HandleRefModel):

    """
    Describes a payment option linked to a billing contact
    """

    billing_contact = models.ForeignKey(
        BillingContact, on_delete=models.CASCADE, related_name="payment_method_set"
    )
    custom_name = models.CharField(max_length=255, null=True, blank=True)
    processor = models.CharField(max_length=255)
    data = models.JSONField(default=dict, blank=True)

    holder = models.CharField(max_length=255)
    country = CountryField()
    city = models.CharField(max_length=255)
    address1 = models.CharField(max_length=255)
    address2 = models.CharField(max_length=255, null=True, blank=True)
    postal_code = models.CharField(max_length=255)
    state = models.CharField(max_length=255, null=True, blank=True)
    status = models.CharField(
        max_length=32,
        choices=(
            ("unconfirmed", "Unconfirmed"),
            ("ok", "Ok"),
            ("inactive", "Inactive"),
        ),
        default="unconfirmed",
    )

    class HandleRef:
        tag = "payment_method"

    class Meta:
        db_table = "billing_payment_method"
        verbose_name = _("Payment Method")
        verbose_name_plural = _("Payment Methods")

    @classmethod
    def get_for_org(cls, org, status="ok"):
        if status:
            return cls.objects.filter(
                billing_contact__org=org, status=status, billing_contact__status=status
            )
        else:
            return cls.objects.filter(billing_contact__org=org)

    @property
    def name(self):
        if self.custom_name:
            return f"{self.billing_contact.name}: {self.custom_name}"

        return f"{self.billing_contact.name}: {self.processor}-{self.id}"

    @property
    def processor_instance(self):
        processor_cls = billing.payment_processors.PROCESSORS.get(self.processor)
        return processor_cls(self)

    def __str__(self):
        return self.name


@reversion.register()
class PaymentCharge(HandleRefModel):
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        related_name="payment_charge_set",
        null=True,
    )
    price = models.DecimalField(
        default=0.0,
        max_digits=8,
        decimal_places=2,
        help_text=_("Price attributed to subscription_cycle for this product"),
    )
    description = models.CharField(max_length=255, null=True, blank=True)
    data = models.JSONField(default=dict, blank=True, help_text=_("Any extra data"))
    failure_notified = models.DateTimeField(
        null=True,
        blank=True,
        help_text=_("When billing contact was notified of failure"),
    )

    status = models.CharField(
        max_length=32,
        choices=[
            ("pending", _("Pending")),
            ("ok", _("Ok")),
            ("failed", _("Failed")),
        ],
        default="pending",
    )

    class Meta:
        db_table = "billing_charge"
        verbose_name = _("Payment Charge")
        verbose_name_plural = _("Payment Charges")

    class HandleRef:
        tag = "payment_charge"

    @property
    def details(self):
        """
        Will attempt to generate charge details from the related
        subscription or one time purchase.
        """

        details = [self.description, ""]

        if self.subscription_cycle_charge:
            cycle = self.subscription_cycle_charge.subscription_cycle
            details += [f"Period {cycle.start} - {cycle.end}", ""]

        for invoice_line in self.invoice_lines:
            details.append(
                f"{invoice_line.description} - {invoice_line.currency} {invoice_line.amount}"
            )

        return "\n".join(details)

    @property
    def org(self):
        return self.payment_method.billing_contact.org

    @property
    def invoice_number(self):
        try:
            return self.invoice.invoice_number
        except Invoice.DoesNotExist:
            pass

        if self.subscription_cycle_charge:
            return self.subscription_cycle_charge.invoice_number

    @property
    def order_number(self):
        try:
            return (
                InvoiceLine.objects.filter(invoice__invoice_number=self.invoice_number)
                .first()
                .order_number
            )
        except AttributeError:
            return None

    @property
    def invoice_lines(self):
        invoice_number = self.invoice_number
        if not invoice_number:
            return []
        return InvoiceLine.objects.filter(invoice__invoice_number=invoice_number)

    def __str__(self):
        if self.payment_method:
            return f"{self.payment_method.name} Charge {self.id}"
        else:
            return f"[Payment Method Removed] Charge {self.id}"

    @reversion.create_revision()
    def capture(self):
        self.status = "ok"
        self.save()

        try:
            self.invoice
        except Invoice.DoesNotExist:
            invoice = Invoice.objects.get(invoice_number=self.invoice_number)
            invoice.charge_object = self
            invoice.status = "ok"
            invoice.save()

        OrderHistory.create_from_payment_charge(self)

    @reversion.create_revision()
    def sync_status(self, commit=True):
        if self.status == "pending":
            if commit:
                self.payment_method.processor_instance.sync_charge(self)
            if self.status == "ok":
                self.capture()

        if self.status == "ok":
            self.create_payment_transaction()

        return self.status

    @reversion.create_revision()
    def create_payment_transaction(self):
        try:
            return self.payment_transaction
        except Payment.DoesNotExist:
            pass

        charge = self
        org = self.org
        invoice_number = self.invoice_number

        payment = Payment.objects.create(
            org=org,
            charge_object=self,
            amount=charge.price,
            billing_contact=charge.payment_method.billing_contact,
            payment_method=charge.payment_method,
            invoice_number=invoice_number,
            order_number=self.order_number,
            payment_processor_txn_id=self.data.get("processor_txn_id", ""),
        )
        return payment

    @reversion.create_revision()
    def notify_failure(self):
        """
        Notify billing contact of failure
        """

        if self.status == "ok":
            return

        if self.failure_notified:
            return

        self.failure_notified = timezone.now()

        notification = render(
            None,
            "billing/email/payment-failure.txt",
            {
                "payment_charge": self,
                "payment_method": self.payment_method,
                "billing_contact": self.payment_method.billing_contact,
                "org": self.org,
                "support_email": settings.SUPPORT_EMAIL,
            },
        ).content.decode("utf-8")

        # notification to the customer
        if settings.BILLING_NOTIFY_FAILURE_CUSTOMER:
            self.payment_method.billing_contact.notify(
                "Payment Failure",
                notification,
            )

        # notification to staff
        if settings.BILLING_NOTIFY_FAILURE_STAFF:
            email(
                settings.BILLING_EMAIL,
                [settings.BILLING_EMAIL],
                f"Payment Failure for {self.org.name}",
                notification,
            )

        self.save()


@reversion.register
class Order(HandleRefModel):

    """
    Describes an order
    """

    org = models.ForeignKey(
        account.models.Organization,
        on_delete=models.PROTECT,
        related_name="order_set",
        null=True,
    )

    order_number = models.CharField(max_length=255, default=unique_order_id)

    class HandleRef:
        tag = "order"

    class Meta:
        db_table = "billing_order"
        verbose_name = _("Order")
        verbose_name_plural = _("Orders")

    def __str__(self):
        return f"{self.org.name} Order {self.order_number}"

    @property
    def price(self):
        price = 0
        for order_line in self.order_line_set.all():
            price += order_line.price
        return price

    @property
    def payment_method(self):
        payment_method = (
            PaymentMethod.get_for_org(self.org).order_by("-created").first()
        )
        return payment_method

    @transaction.atomic
    def create_invoice(self, create_processor_invoice=True):
        try:
            return self.invoice
        except Invoice.DoesNotExist:
            pass

        invoice = Invoice.objects.create(
            org=self.org,
            order=self,
            status="pending",
        )

        for order_line in self.order_line_set.all():
            InvoiceLine.objects.create(
                amount=order_line.amount,
                subscription=order_line.subscription,
                subscription_cycle_product=order_line.subscription_cycle_product,
                product=order_line.product,
                description=order_line.description,
                invoice=invoice,
            )

        # payment method isn't used to charge the invoice, but we need it to create the invoice in the payment processor
        # as it holds the customer data
        payment_method = self.payment_method

        if not payment_method:
            raise OSError("No payment method found for org")

        if not create_processor_invoice:
            return

        # this creates an invoice in the payment processor (stripe)
        payment_method.processor_instance.create_invoice(
            invoice, charge_automatically=False
        )


@reversion.register
class Invoice(HandleRefModel):

    """
    Describes an invoice
    """

    org = models.ForeignKey(
        account.models.Organization,
        on_delete=models.PROTECT,
        related_name="invoice_set",
        null=True,
    )

    order = models.OneToOneField(
        Order,
        on_delete=models.PROTECT,
        related_name="invoice",
    )

    charge_object = models.OneToOneField(
        PaymentCharge,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="invoice",
    )

    invoice_number = models.CharField(max_length=255, default=unique_invoice_id)

    data = models.JSONField(default=dict, blank=True, help_text=_("Any extra data"))

    status = models.CharField(
        max_length=32,
        choices=[
            ("pending", _("Pending")),
            ("ok", _("Paid")),
            ("failed", _("Failed")),
        ],
        default="pending",
    )

    class HandleRef:
        tag = "invoice"

    class Meta:
        db_table = "billing_invoice"
        verbose_name = _("Invoice")
        verbose_name_plural = _("Invoices")

    def __str__(self):
        return f"{self.org.name} Invoice {self.invoice_number}"

    @property
    def payment_method(self):
        payment_method = (
            PaymentMethod.get_for_org(self.org).order_by("-created").first()
        )
        return payment_method

    @property
    def price(self):
        price = 0
        for invoice_line in self.invoice_line_set.all():
            price += invoice_line.price
        return price

    @property
    def currency(self):
        try:
            return self.invoice_line_set.first().currency
        except AttributeError:
            return "USD"

    @property
    def paid(self):
        """
        Date this invoice was paid
        """

        try:
            return (
                Payment.objects.filter(invoice_number=self.invoice_number)
                .first()
                .created
            )
        except AttributeError:
            return None

    @property
    def details(self):
        """
        Will attempt to generate charge details from the related
        subscription or one time purchase.
        """

        details = []

        for invoice_line in self.invoice_line_set.all():
            details.append(f"{invoice_line.description}")

        return "\n".join(details)

    def __str__(self):
        return f"{self.org.name} Invoice {self.invoice_number}"

    @reversion.create_revision()
    def capture(self):
        """
        Will sync the invoice status from the remote payment
        processor (stripe)
        """

        # TODO probably dont hardcode stripe?
        stripe_payment_intent = self.data.get("stripe_payment_intent")

        # no stipe charge exists for this invoice yet
        # meaning its still open
        if not stripe_payment_intent:
            return

        # payment method on stripe's side
        processor_payment_method = stripe_payment_intent["payment_method"]

        # payment method on our side
        payment_method = PaymentMethod.objects.filter(
            billing_contact__org=self.org,
            data__stripe_payment_method=processor_payment_method,
        ).first()

        if not payment_method:
            # we dont have the payment method on our side
            # so we cannot track it
            #
            # invoice will still be marked as paid but we
            # need to defer to stripe for further charge
            # details
            return

        # create a payment charge entry on our side
        # based on the stripe charge tied to the invoice
        charge = PaymentCharge.objects.create(
            payment_method=payment_method,
            price=stripe_payment_intent["amount"] / 100,
            description=stripe_payment_intent["description"],
            data={
                "stripe_payment_intent": stripe_payment_intent["id"],
                "processor_txn_id": stripe_payment_intent["id"],
                "receipt_url": stripe_payment_intent["receipt_url"],
            },
        )

        # link the charge to the invoice
        self.charge_object = charge
        self.save()

    @reversion.create_revision()
    def sync_status(self, commit=True):
        if self.status == "pending":
            # invoice is still open

            if commit:
                # sync invoice status from stripe
                self.payment_method.processor_instance.sync_invoice(self)

            if self.status == "ok":
                # invoice has been paid, capture the payment
                # on our side

                self.capture()

                # we also need to sync payment charge status

                self.charge_object.sync_status(commit=commit)

        return self.status


class Transaction(HandleRefModel):
    # Should this be auto_now_add ? Or is default=now better.
    created = models.DateTimeField(
        help_text=_("When transaction was created."), default=timezone.now
    )
    currency = models.CharField(
        max_length=255, choices=const.CURRENCY_TYPES, default="USD"
    )
    amount = models.DecimalField(max_digits=8, decimal_places=2, blank=False)
    transaction_id = models.UUIDField(default=uuid.uuid4, editable=False)

    class Meta:
        abstract = True


class MoneyTransaction(Transaction):
    billing_contact = models.ForeignKey(
        "billing.BillingContact",
        on_delete=models.PROTECT,
        related_name="%(class)s_money_transaction_set",
        null=True,
    )
    payment_method = models.ForeignKey(
        "billing.PaymentMethod",
        on_delete=models.SET_NULL,
        null=True,
        related_name="%(class)s_payment_method",
        help_text=_("User payment option that will be charged by this transaction"),
    )

    payment_processor_txn_id = models.CharField(blank=True, max_length=255)

    class Meta:
        abstract = True


@reversion.register()
class OrderLine(Transaction):
    order = models.ForeignKey(
        "billing.Order", on_delete=models.CASCADE, related_name="order_line_set"
    )

    product = models.ForeignKey(
        "billing.Product", on_delete=models.PROTECT, related_name="order_set", null=True
    )
    subscription = models.ForeignKey(
        "billing.Subscription",
        on_delete=models.PROTECT,
        related_name="order_set",
        null=True,
        blank=True,
    )
    subscription_cycle_product = models.ForeignKey(
        "billing.SubscriptionCycleProduct",
        on_delete=models.SET_NULL,
        related_name="order_set",
        null=True,
        blank=True,
    )
    description = models.TextField(blank=True)

    class HandleRef:
        tag = "order_line"

    class Meta:
        db_table = "billing_order_line"
        verbose_name = _("Order Line")
        verbose_name_plural = _("Order Lines")

    @property
    def order_number(self):
        return self.order.order_number

    @property
    def org(self):
        return self.order.org


@reversion.register()
class InvoiceLine(Transaction):
    invoice = models.ForeignKey(
        "billing.Invoice",
        on_delete=models.CASCADE,
        related_name="invoice_line_set",
    )

    product = models.ForeignKey(
        "billing.Product",
        on_delete=models.PROTECT,
        related_name="invoice_set",
        null=True,
        blank=True,
    )
    subscription = models.ForeignKey(
        "billing.Subscription",
        on_delete=models.PROTECT,
        related_name="invoice_set",
        blank=True,
        null=True,
    )
    subscription_cycle_product = models.ForeignKey(
        "billing.SubscriptionCycleProduct",
        on_delete=models.SET_NULL,
        related_name="invoice_set",
        blank=True,
        null=True,
    )
    description = models.TextField(blank=True)

    class HandleRef:
        tag = "invoice_line"

    class Meta:
        db_table = "billing_invoice_line"
        verbose_name = _("Invoice Line")
        verbose_name_plural = _("Invoice Lines")

    @property
    def paid(self):
        """
        Date this invoice was paid
        """

        try:
            return (
                Payment.objects.filter(invoice_number=self.invoice_number)
                .first()
                .created
            )
        except AttributeError:
            return None

    @property
    def invoice_number(self):
        return self.invoice.invoice_number

    @property
    def order_number(self):
        return self.invoice.order.order_number

    @property
    def org(self):
        return self.invoice.org


@reversion.register()
class Payment(MoneyTransaction):
    org = models.ForeignKey(
        account.models.Organization,
        on_delete=models.PROTECT,
        related_name="payment_transaction_set",
    )
    invoice_number = models.CharField(blank=True, max_length=255)
    order_number = models.CharField(blank=True, max_length=255)
    charge_object = models.OneToOneField(
        PaymentCharge,
        null=True,
        on_delete=models.PROTECT,
        related_name="payment_transaction",
    )

    class HandleRef:
        tag = "payment"

    class Meta:
        db_table = "billing_payment"
        verbose_name = _("Payment")
        verbose_name_plural = _("Payments")


@reversion.register()
class Deposit(MoneyTransaction):
    org = models.ForeignKey(
        account.models.Organization,
        on_delete=models.PROTECT,
        related_name="deposit_transaction_set",
    )

    class HandleRef:
        tag = "deposit"

    class Meta:
        db_table = "billing_deposit"
        verbose_name = _("Deposit")
        verbose_name_plural = _("Deposits")


@reversion.register()
class Withdrawal(MoneyTransaction):
    org = models.ForeignKey(
        account.models.Organization,
        on_delete=models.PROTECT,
        related_name="withdrawal_transaction_set",
    )

    class HandleRef:
        tag = "withdrawal"

    class Meta:
        db_table = "billing_withdrawal"
        verbose_name = _("Withdrawal")
        verbose_name_plural = _("Withdrawals")


@reversion.register()
class Ledger(HandleRefModel):
    org = models.ForeignKey(
        account.models.Organization,
        on_delete=models.PROTECT,
        related_name="ledger",
        null=True,
    )

    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey("content_type", "object_id")

    invoice_number = models.CharField(blank=True, null=True, max_length=255)
    order_number = models.CharField(blank=True, null=True, max_length=255)

    class HandleRef:
        tag = "ledger"

    class Meta:
        db_table = "billing_ledgers"
        verbose_name = _("Ledger")
        verbose_name_plural = _("Ledger")
