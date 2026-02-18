import datetime
import urllib.parse

import reversion
from django.conf import settings

from billing.payment_processors.processor import PaymentProcessor


class PaypalProcessor(PaymentProcessor):
    id = "paypal"
    name = "PayPal"

    @classmethod
    def agreement_token(cls, request):
        return request.GET.get("token")

    @property
    def agreement_process_redirect(self):
        return self.user_payment_opt.data.get("approval_url")

    def __init__(self, user_payment_opt, **kwargs):
        self.plan_id = user_payment_opt.data.get("plan_id")
        self.plan = None
        self.agreement = None

        if settings.PAYPAL_MODE == "live":
            self.paypal_env = paypal.environment.LiveEnvironment(
                settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET
            )
        else:
            self.paypal_env = paypal.environment.SandboxEnvironment(
                settings.PAYPAL_CLIENT_ID, settings.PAYPAL_SECRET
            )

        super().__init__(user_payment_opt, **kwargs)

    def require_billing_plan(self, subscriptions, **kwargs):
        if self.plan_id:
            return self.plan_id

        setup_fee = 0.0

        for subscription in subscriptions:
            setup_fee += float(subscription.product.price)

        payload = {
            "description": self.agreement_description,
            "merchant_preferences": {
                "auto_bill_amount": "yes",
                "cancel_url": self.agreement_cancel_url,
                "initial_fail_amount_action": "continue",
                "max_fail_attempts": "1",
                "return_url": self.agreement_success_url,
            },
            "name": "plan-{}".format(self.agreement_name.lower().replace(" ", "-")),
            "payment_definitions": [],
            "type": "INFINITE",
        }

        payload["merchant_preferences"]["setup_fee"] = {
            "currency": self.default_currency,
            "value": f"{setup_fee:.2f}",
        }

        for subscription in subscriptions:
            payload["payment_definitions"].append(
                self.subscription_to_paydef(subscription)
            )

        billing_plan = BillingPlan(payload, api=self.paypal_api)

        if billing_plan.create():
            self.plan_id = billing_plan.id
            billing_plan.activate()
            billing_plan = BillingPlan.find(self.plan_id, api=self.paypal_api)
            self.plan = billing_plan
            self.user_payment_opt.data["plan_id"] = self.plan_id
            self.user_payment_opt.save()
        else:
            raise OSError(billing_plan.error)

        return self.plan_id

    def require_billing_agreement(self):
        now = datetime.datetime.now() + datetime.timedelta(minutes=1)
        now_str = now.strftime("%Y-%m-%dT%H:%M:%SZ")
        payload = {
            "name": self.agreement_name,
            "description": self.agreement_description,
            "start_date": now_str,
            "plan": {"id": self.plan_id},
            "payer": {"payment_method": "paypal"},
        }
        billing_agreement = BillingAgreement(payload, api=self.paypal_api)

        if billing_agreement.create():
            for link in billing_agreement.links:
                if link.rel == "approval_url":
                    url_query = urllib.parse.urlsplit(link.href).query
                    url_query = dict(urllib.parse.parse_qsl(url_query))

                    self.user_payment_opt.data.update(approval_url=link.href)
                    self.user_payment_opt.token = url_query.get("token")
                    self.user_payment_opt.status = "pending"

                    self.user_payment_opt.save()
        else:
            raise OSError(billing_agreement.error)

    def subscription_to_paydef(self, subscription):
        return {
            "amount": {
                "currency": self.default_currency,
                "value": f"{subscription.price:.2f}",
            },
            "subscription_cycles": "0",
            "frequency": subscription.subscription_cycle.upper(),
            "frequency_interval": f"{subscription.subscription_cycle_frequency}",
            "name": subscription.product.description,
            "type": "REGULAR",
        }

    @reversion.create_revision()
    def create_agreement(self, subscriptions, **kwargs):
        self.require_billing_plan(subscriptions, **kwargs)
        self.require_billing_agreement()
        self.user_payment_opt.stats = "pending"
        self.user_payment_opt.save()

    def update_agreement(self):
        billing_plan = BillingPlan.find(self.plan_id, api=self.paypal_api)
        subscriptions = self.user_payment_opt.subscription_set.all()
        paydef = [
            self.subscription_to_paydef(subscription) for subscription in subscriptions
        ]
        payload = [{"op": "replace", "path": "/payment_definitions/0", "value": paydef}]
        print(billing_plan["payment_definitions"])

        print(payload)

        if not billing_plan.replace(payload):
            raise OSError(billing_plan.error)
