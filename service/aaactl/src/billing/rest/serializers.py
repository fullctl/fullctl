import reversion
from django.utils.translation import gettext as _
from phonenumber_field.phonenumber import PhoneNumber
from phonenumbers.phonenumberutil import NumberParseException
from rest_framework import serializers

import billing.forms as forms
import billing.models as models
import billing.payment_processors as processors
from account.rest.serializers import FormValidationMixin


class Serializers:
    pass


HANDLEREF_FIELDS = ["id", "status", "created", "updated"]


def register(cls):
    if not hasattr(cls, "ref_tag"):
        cls.ref_tag = cls.Meta.model.HandleRef.tag
        cls.Meta.fields += HANDLEREF_FIELDS
    setattr(Serializers, cls.ref_tag, cls)
    return cls


def is_valid_phone_number(phone_number, country):
    try:
        phone_number = PhoneNumber.from_string(phone_number, region=country)
    except NumberParseException:
        return False
    return phone_number.is_valid()


@register
class Product(serializers.ModelSerializer):
    class Meta:
        model = models.Product

        fields = ["name", "component", "description", "group", "price"]


@register
class OrganizationProduct(serializers.ModelSerializer):
    class Meta:
        model = models.OrganizationProduct
        fields = ["org", "product", "expires"]


@register
class RecurringProduct(serializers.ModelSerializer):
    product = Product(read_only=True)

    class Meta:
        model = models.RecurringProduct

        fields = ["product", "type", "price", "unit"]


@register
class Invoice(serializers.ModelSerializer):
    class Meta:
        model = models.Invoice
        fields = [
            "org",
            "invoice_number",
            "price",
            "currency",
        ]


@register
class PaymentMethod(serializers.ModelSerializer):
    country = serializers.CharField()

    class Meta:
        model = models.PaymentMethod
        fields = [
            "billing_contact",
            "custom_name",
            "name",
            "holder",
            "country",
            "city",
            "address1",
            "address2",
            "postal_code",
            "state",
        ]


@register
class BillingContact(FormValidationMixin, serializers.ModelSerializer):
    form = forms.BillingContactForm
    required_context = []

    phone_number = serializers.CharField()
    phone_number_country = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = models.BillingContact
        fields = ["name", "email", "phone_number", "phone_number_country"]

    def validate(self, data):
        if not is_valid_phone_number(
            data.get("phone_number"), data.get("phone_number_country")
        ):
            raise serializers.ValidationError(
                {"phone_number": _("Invalid phone number")}
            )

        # format data for FormValidationMixin
        # PhoneField with PhoneNumberPrefixWidget expects phone_number_0 and phone_number_1
        form_formatted_data = data.copy()
        form_formatted_data["phone_number_0"] = form_formatted_data.pop(
            "phone_number_country"
        )
        form_formatted_data["phone_number_1"] = form_formatted_data.pop("phone_number")
        super().validate(form_formatted_data)

        return data

    def save(self):
        data = self.validated_data
        phone_number = PhoneNumber.from_string(
            data["phone_number"], region=data["phone_number_country"]
        )
        data["phone_number"] = phone_number
        data.pop("phone_number_country", None)

        return super().save()


@register
class OrderHistory(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    billing_contact = BillingContact()

    class Meta:
        model = models.OrderHistory
        fields = [
            "order_id",
            "description",
            "price",
            "processed",
            "items",
            "billing_contact",
        ]

    def get_items(self, order_history):
        return [
            {"description": item.description, "price": item.price}
            for item in order_history.order_history_item_set.all()
        ]


@register
class Subscription(serializers.ModelSerializer):
    recurring_product = RecurringProduct(read_only=True)
    items = serializers.SerializerMethodField()
    subscription_cycle = serializers.SerializerMethodField()
    name = serializers.CharField(read_only=True, source="group.name")

    class Meta:
        model = models.Subscription
        fields = [
            "name",
            "recurring_product",
            "org",
            "subscription_cycle_interval",
            "subscription_cycle",
            "payment_method",
            "items",
        ]

    def get_subscription_cycle(self, subscription):
        if not subscription.subscription_cycle:
            return None
        return {
            "start": subscription.subscription_cycle.start,
            "end": subscription.subscription_cycle.end,
        }

    def get_items(self, subscription):
        if not subscription.subscription_cycle:
            return []
        return [
            {
                "description": subscription_product.description,
                "type": subscription_product.product.recurring_product.type_description,
                "usage": subscription_product.subscription_cycle_usage,
                "cost": subscription_product.subscription_cycle_cost,
                "name": subscription_product.product.name,
                "unit_name": subscription_product.product.recurring_product.unit,
                "unit_name_plural": subscription_product.product.recurring_product.unit_plural,
                "expiration_date": subscription_product.expires,
            }
            for subscription_product in subscription.subscription_product_set.all()
        ]


@register
class BillingSetup(serializers.Serializer):
    ref_tag = "setup"

    required_billing_address_fields = [
        "holder",
        "phone_number",
        "phone_number_country",
    ]

    # Setup init data (forms.BillingSetupInitForm)

    product = serializers.CharField(required=False)
    redirect = serializers.CharField(required=False, allow_blank=True)

    # Payment option (forms.SelectPaymentMethodForm)

    payment_method = serializers.CharField(
        required=False, allow_null=True, allow_blank=True
    )
    payment_method_id = serializers.SerializerMethodField()

    # Billing address (forms.BillingContactDetails)
    # Only needed when a new payment option is being created

    holder = serializers.CharField(required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone_number = serializers.CharField(required=False, allow_blank=True)
    phone_number_country = serializers.CharField(required=False, allow_blank=True)
    country = serializers.CharField(required=False, allow_blank=True)
    city = serializers.CharField(required=False, allow_blank=True)
    state = serializers.CharField(required=False, allow_blank=True)
    address1 = serializers.CharField(required=False, allow_blank=True)
    address2 = serializers.CharField(required=False, allow_blank=True)
    postal_code = serializers.CharField(required=False, allow_blank=True)

    # agreements

    agreement_tos = serializers.BooleanField(required=True)

    def get_payment_method_id(self, data):
        if data.get("payment_method"):
            return data["payment_method"].id

    def validate_product(self, value):
        try:
            return models.Product.objects.get(name=value)
        except models.Product.DoesNotExist:
            raise serializers.ValidationError("Unknown product")

    def validate_payment_method(self, value):
        org = self.context.get("org")
        if not value:
            return 0
        try:
            return models.PaymentMethod.objects.get(id=value, billing_contact__org=org)
        except models.PaymentMethod.DoesNotExist:
            raise serializers.ValidationError("Payment method not found")

    def validate(self, data):
        super().validate(data)
        org = self.context.get("org")

        if not data.get("payment_method"):
            if not is_valid_phone_number(
                data.get("phone_number"), data.get("phone_number_country")
            ):
                raise serializers.ValidationError(
                    {"phone_number": _("Invalid phone number")}
                )
            phone_number = PhoneNumber.from_string(
                data["phone_number"], region=data["phone_number_country"]
            )

            field_errors = {}
            for field in self.required_billing_address_fields:
                if not data.get(field):
                    field_errors[field] = _("Input required")
            if field_errors:
                raise serializers.ValidationError(field_errors)

            data["phone_number"] = phone_number
            data.pop("phone_number_country", None)

            billing_contact, created = models.BillingContact.objects.get_or_create(
                org=org,
                name=data.get("holder"),
                email=data.get("email"),
                phone_number=data.get("phone_number"),
                status="ok",
            )
            if created:
                try:
                    billing_contact.full_clean()
                except models.ValidationError as e:
                    billing_contact.delete()
                    raise serializers.ValidationError(e.message_dict)

            data["payment_method"] = models.PaymentMethod(
                billing_contact=billing_contact
            )

        processor = data["processor"] = processors.default()(data["payment_method"])

        if not data["payment_method"].id and processor.Form:
            form = processor.Form(self.context.get("data"))
            if not form.is_valid():
                raise serializers.ValidationError(form.errors)
            data["processor_data"] = form.cleaned_data
        else:
            data["processor_data"] = {}

        # agreement_tos needs to be True

        if not data.get("agreement_tos"):
            raise serializers.ValidationError(
                {"agreement_tos": _("You need to agree to the Terms of Service")}
            )

        return data

    @reversion.create_revision()
    def save(self):
        data = self.validated_data

        payment_method = data["payment_method"]
        processor = data["processor"]
        product = data.get("product")
        user = self.context.get("user")
        org = self.context.get("org")

        reversion.set_user(user)
        reversion.set_comment("Billing setup completed")

        if not payment_method.id:
            payment_method.processor = processor.id
            for field in self.required_billing_address_fields:
                setattr(payment_method, field, data.get(field))
            payment_method.save()

        if product and product.is_recurring_product:
            subscription = models.Subscription.get_or_create(
                org,
                product.group,
                # TODO: allow to specify?
                "month",
            )
            subscription.payment_method = payment_method
            subscription.save()

            if not subscription.subscription_cycle:
                subscription.start_subscription_cycle()

            if not subscription.subscription_product_set.filter(
                product=product
            ).exists():
                subscription.add_product(product)

        models.Subscription.set_payment_method(org, payment_method)

        processor.setup_billing(**data.get("processor_data"))
