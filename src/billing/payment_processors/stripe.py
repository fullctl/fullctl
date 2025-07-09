import reversion
import stripe
from django import forms
from django.conf import settings
from django.utils.translation import gettext as _

from billing.payment_processors.processor import (
    InternalProcessorError,
    PaymentProcessor,
)

stripe.api_key = settings.STRIPE_SECRET_KEY


class LegacyPaymentMethodDetected(InternalProcessorError):
    def __init__(self):
        super().__init__("Legacy payment method detected - no longer supported")


def payment_method_name(stripe_payment_method_id):
    """
    Returns the name of a stripe payment method based on the type

    Currently supports card and us_bank_account
    """

    stripe_pm = stripe.PaymentMethod.retrieve(stripe_payment_method_id)

    if stripe_pm.type == "card":
        pm_name = stripe_pm.card.brand + " " + stripe_pm.card.last4
    elif stripe_pm.type == "us_bank_account":
        pm_name = (
            stripe_pm.us_bank_account.bank_name + " " + stripe_pm.us_bank_account.last4
        )
    else:
        pm_name = None

    return pm_name


class Stripe(PaymentProcessor):
    id = "stripe"
    name = _("Stripe")

    class Form(forms.Form):
        client_secret = forms.CharField(widget=forms.HiddenInput())
        setup_intent_id = forms.CharField(widget=forms.HiddenInput())

        @property
        def template(self):
            return "billing/setup/stripe-elements.html"

    @property
    def source(self):
        return self.data.get("stripe_payment_method")

    @property
    def customer(self):
        return self.billing_contact_customer.data.get("stripe_customer")

    @property
    def form(self):
        return self.Form()

    @classmethod
    def public_key(self):
        return settings.STRIPE_PUBLIC_KEY

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.api_key = settings.STRIPE_SECRET_KEY

    def setup_customer(self):
        # check if customer has already been created
        # on stripe's end

        if self.customer:
            return self.customer

        customer = stripe.Customer.create(
            description=f"billing_contact{self.payment_method.billing_contact.id}",
            name=self.payment_method.billing_contact.name,
            email=self.payment_method.billing_contact.email,
            api_key=self.api_key,
        )

        self.billing_contact_customer.data["stripe_customer"] = customer["id"]
        self.save()

        return customer["id"]

    def setup_unconfirmed_payment_method(self, client_secret, setup_intent_id):
        self.setup_customer()

        self.payment_method.status = "unconfirmed"

        self.data["stripe_setup_intent"] = setup_intent_id
        self.data["stripe_client_secret"] = client_secret

        self.save()

        return self.payment_method.id

    def link_customer(self):
        print("linking customer")
        print(self.source, self.customer)

        stripe.PaymentMethod.attach(
            self.source,
            customer=self.customer,
        )

    @reversion.create_revision()
    def setup_billing(self, **kwargs):
        if self.source:
            self.payment_method.status = "ok"
            self.save()
            return
        self.setup_unconfirmed_payment_method(**kwargs)

    @reversion.create_revision()
    def charge(self, payment_charge):
        if not self.source:
            raise ValueError("Payment method not setup.")

        payment_intent = None

        if self.source.startswith("card_"):
            raise LegacyPaymentMethodDetected()

        # Ensure a stable idempotency key for this payment charge across retries
        idemp_key = payment_charge.data.get("idemp_key")
        if not idemp_key:
            # Use the payment_charge primary key to keep it unique and deterministic
            idemp_key = f"cycle-{payment_charge.id}"
            payment_charge.data["idemp_key"] = idemp_key
            payment_charge.save(update_fields=["data"])

        try:
            payment_intent = stripe.PaymentIntent.create(
                amount=int(payment_charge.price * 100),
                currency=self.default_currency,
                description=payment_charge.details,
                customer=self.customer,
                payment_method=self.source,
                confirm=True,
                automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
                payment_method_options=None,
                idempotency_key=idemp_key,
                api_key=self.api_key,
            )
            self.log.info(
                "stripe payment intent", status="ok", payment_intent=payment_intent
            )

        except Exception as e:
            # failed to charge on the stripe end, log the error
            # and mark the charge as failed
            payment_charge.status = "failed"
            payment_charge.data["processor_failure"] = str(e)
            payment_charge.save()
            self.log.error(
                "stripe payment intent",
                status="failed",
                payment_charge=payment_charge,
                error=e,
            )
            return

        payment_charge.status = "pending"

        payment_charge.data["stripe_payment_intent"] = payment_intent["id"]
        payment_charge.data["processor_txn_id"] = payment_intent["id"]

        if payment_intent.get("latest_charge"):
            payment_charge.data["receipt_url"] = stripe.Charge.retrieve(
                payment_intent["latest_charge"]
            )["receipt_url"]

        payment_charge.save()

    def _sync_charge(self, payment_charge, status=None):
        reversion.set_comment("Stripe charge status sync")

        if not payment_charge.data.get("stripe_payment_intent"):
            return super()._sync_charge(payment_charge, "failed")

        payment_intent = stripe.PaymentIntent.retrieve(
            payment_charge.data["stripe_payment_intent"], api_key=self.api_key
        )

        if payment_intent["status"] == "succeeded":
            # set receupt url from latest_charge
            if payment_intent.get("latest_charge"):
                payment_charge.data["receipt_url"] = stripe.Charge.retrieve(
                    payment_intent["latest_charge"]
                )["receipt_url"]
            return super()._sync_charge(payment_charge, "ok")

        elif payment_intent["status"] == "failed":
            return super()._sync_charge(payment_charge, "failed")

    def _sync_invoice(self, invoice, **kwargs):
        reversion.set_comment("Stripe invoice status sync")

        if not invoice.data.get("stripe_invoice"):
            return super()._sync_invoice(invoice, "failed")

        stripe_invoice = stripe.Invoice.retrieve(
            invoice.data["stripe_invoice"], api_key=self.api_key
        )

        if not stripe_invoice["payment_intent"]:
            return

        stripe_payment_intent = stripe.Charge.retrieve(
            stripe_invoice["payment_intent"], api_key=self.api_key
        )

        if stripe_invoice["status"] == "paid":
            invoice.data["stripe_payment_intent"] = stripe_payment_intent

            return super()._sync_invoice(invoice, "ok")

        elif stripe_invoice["status"] == "uncollectible":
            return super()._sync_invoice(invoice, "failed")

    def create_invoice(self, invoice, charge_automatically=False):
        """
        Creates a strip invoice from a aaactl Invoice instance
        """

        # If the invoice has already been created on Stripe we simply return
        # the existing invoice object instead of erroring out. This makes the
        # operation idempotent – important when `SubscriptionCycle.charge()`
        # is retried and wants to ensure an invoice exists.

        if invoice.data.get("stripe_invoice"):
            try:
                return stripe.Invoice.retrieve(
                    invoice.data["stripe_invoice"], api_key=self.api_key
                )
            except Exception:
                # If Stripe can't find the invoice we fall through to create
                # a fresh copy to keep accounting consistent.
                pass

        for invoice_line in invoice.invoice_line_set.all():
            stripe.InvoiceItem.create(
                customer=self.customer,
                amount=int(invoice_line.amount * 100),
                currency=invoice_line.currency,
                description=invoice_line.description,
                api_key=self.api_key,
            )

        stripe_invoice = stripe.Invoice.create(
            customer=self.customer,
            days_until_due=30,
            api_key=self.api_key,
            description="FullCtl Invoice",
            collection_method="charge_automatically"
            if charge_automatically
            else "send_invoice",
        )

        stripe.Invoice.finalize_invoice(
            stripe_invoice["id"],
            api_key=self.api_key,
        )

        invoice.data["stripe_invoice"] = stripe_invoice["id"]
        invoice.save()

        return stripe_invoice
