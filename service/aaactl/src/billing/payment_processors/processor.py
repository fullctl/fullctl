"""
Payment processor interface
"""

import reversion
import structlog
from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist
from django.urls import reverse
from fullctl.django.util import host_url

MAP = {}


def register(cls):
    MAP[cls.id] = cls
    return cls


def get_processor(_id):
    return MAP[_id]


class InternalProcessorError(OSError):
    pass


class PaymentProcessor:
    id = "_processor"
    name = "Payment Processor Interface"

    @property
    def agreement_cancel_url(self):
        return "{}{}".format(
            host_url(), reverse("billing:agreement-cancel", args=(self.id,))
        )

    @property
    def agreement_success_url(self):
        return "{}{}".format(
            host_url(), reverse("billing:agreement-success", args=(self.id,))
        )

    @property
    def default_currency(self):
        return settings.BILLING_DEFAULT_CURRENCY

    @property
    def agreement_name(self):
        return settings.BILLING_AGREEMENT_NAME

    @property
    def agreement_description(self):
        return settings.BILLING_AGREEMENT_DESCRIPTION

    @property
    def billing_contact(self):
        return self.payment_method.billing_contact

    @property
    def billing_contact_customer(self):
        try:
            return self.payment_method.billing_contact.customer
        except ObjectDoesNotExist:
            from billing.models import CustomerData

            customer, created = CustomerData.objects.get_or_create(
                billing_contact=self.billing_contact
            )
            return customer

    @property
    def data(self):
        return self.payment_method.data

    def __init__(self, payment_method, **kwargs):
        self.payment_method = payment_method
        self.log = structlog.get_logger("django")

    def save(self):
        self.payment_method.save()
        self.billing_contact_customer.save()

    @reversion.create_revision()
    def sync_charge(self, payment_charge):
        if payment_charge.status == "pending":
            return self._sync_charge(payment_charge)
        return payment_charge.status

    def _sync_charge(self, payment_charge, status=None):
        if status:
            payment_charge.status = status
            payment_charge.save()

            try:
                payment_charge.subscription_cycle_charge.status = status
                payment_charge.subscription_cycle_charge.save()
            except ObjectDoesNotExist:
                pass

        return status

    @reversion.create_revision()
    def sync_invoice(self, invoice):
        if invoice.status == "pending":
            return self._sync_invoice(invoice)
        return invoice.status

    def _sync_invoice(self, invoice, status=None):
        if status:
            invoice.status = status
            invoice.save()
        return status
