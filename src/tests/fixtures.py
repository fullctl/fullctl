import pytest
from django.test import Client
from grainy.const import PERM_CRUD


class BillingObjects:
    def __init__(self, handle="test"):
        from django.contrib.auth import get_user_model
        from rest_framework.test import APIClient

        from account.models import (
            ManagedPermission,
            ManagedPermissionRoleAutoGrant,
            Organization,
            OrganizationRole,
            Role,
        )
        from billing.models import (
            BillingContact,
            PaymentMethod,
            Product,
            ProductGroup,
            ProductModifier,
            RecurringProduct,
            Subscription,
        )

        self.product_group = ProductGroup.objects.create(
            name="Test Group",
        )

        self.other_product_group = ProductGroup.objects.create(
            name="Other Group",
        )

        self.product = Product.objects.create(
            name="test",
            description="test product",
            group=self.product_group,
            price=10.00,
            data={"foo": "bar"},
        )

        self.product_subscription_fixed = Product.objects.create(
            name="test.subscription.fixed",
            description="test product: fixed subscription",
            group=self.product_group,
            price=0.00,
            data={"foo": "bar"},
        )

        RecurringProduct.objects.create(
            product=self.product_subscription_fixed,
            type="fixed",
            price=125.99,
            data={"foo": "bar"},
        )

        self.product_subscription_metered = Product.objects.create(
            name="test.subscription.metered",
            description="test product: metered subscription",
            group=self.product_group,
            price=0.00,
            data={"foo": "bar"},
        )

        RecurringProduct.objects.create(
            product=self.product_subscription_metered,
            type="metered",
            price=0.50,
            data={"foo": "bar"},
        )

        ProductModifier.objects.create(
            product=self.product,
            type="reduction",
            value=10,
            duration=30,
            code="TESTREDUCTION",
        )

        ProductModifier.objects.create(
            product=self.product,
            type="quantity",
            value=2,
            duration=30,
            code="TESTQUANTITY",
        )

        self.org = Organization.objects.create(
            name="Subscription Org", slug="subscription_org"
        )

        self.monthly_subscription = Subscription.objects.create(
            org=self.org,
            group=self.product_group,
            subscription_cycle_interval="month",
            subscription_cycle_start=None,  # Set none to start
            payment_method=None,  # Set none to start
        )

        self.monthly_subscription.add_product(self.product_subscription_metered)

        self.yearly_subscription = Subscription.objects.create(
            org=self.org,
            group=self.product_group,
            subscription_cycle_interval="year",
            subscription_cycle_start=None,  # Set none to start
            payment_method=None,  # Set none to start
        )

        self.yearly_subscription.add_product(self.product_subscription_metered)

        self.billing_contact = BillingContact.objects.create(
            org=self.org,
            name="William Contact",
            email="billing_contact@localhost",
            phone_number="+16044011234",
        )

        self.payment_method = PaymentMethod.objects.create(
            billing_contact=self.billing_contact,
            custom_name="Test Customer",
            processor="stripe",
            holder="William Contact",
            country="US",
            city="Chicago",
            address1="3400 Test Ave",
            postal_code="60600",
            state="IL",
            data={"stripe_payment_method": "5200828282828210"},
            status="ok",
        )

        self.user = get_user_model().objects.create_user(
            username=f"user_{handle}",
            email=f"{handle}@localhost",
            password="test",
        )
        self.org.add_user(self.user, perms="crud")

        admin_role, _ = Role.objects.get_or_create(
            name="admin",
            description="",
            level=15,
            auto_set_on_creator=True,
            auto_set_on_member=False,
        )

        OrganizationRole.objects.get_or_create(
            org=self.org, user=self.user, role=admin_role
        )

        org_managed_permission, _ = ManagedPermission.objects.get_or_create(
            namespace="org.{org_id}",
            description="",
            group="aaactl",
        )

        ManagedPermissionRoleAutoGrant.objects.get_or_create(
            managed_permission=org_managed_permission,
            role=admin_role,
            permissions=PERM_CRUD,
        )

        user_managed_permission = ManagedPermission.objects.create(
            namespace="user.{org_id}",
            description="",
            group="aaactl",
        )

        ManagedPermissionRoleAutoGrant.objects.create(
            managed_permission=user_managed_permission,
            role=admin_role,
            permissions=PERM_CRUD,
        )

        billing_managed_permission = ManagedPermission.objects.create(
            namespace="billing.{org_id}",
            description="",
            group="aaactl",
        )

        ManagedPermissionRoleAutoGrant.objects.create(
            managed_permission=billing_managed_permission,
            role=admin_role,
            permissions=PERM_CRUD,
        )

        ManagedPermission.apply_roles_all()

        self.api_client = APIClient()
        self.api_client.login(username=self.user.username, password="test")

        self.client = Client()
        self.client.login(username=self.user.username, password="test")


class AccountObjects:
    def __init__(self, handle):
        from django.contrib.auth import get_user_model
        from django_grainy.util import Permissions
        from rest_framework.test import APIClient

        from account.models import (
            ManagedPermission,
            ManagedPermissionRoleAutoGrant,
            Organization,
            OrganizationRole,
            Role,
        )
        from account.models.federation import ServiceFederationSupport
        from whitelabel_fullctl.models import OrganizationBranding

        (
            self.federated_service_support,
            _,
        ) = ServiceFederationSupport.objects.get_or_create(
            name="Test Service",
            slug="test_service",
        )

        self.user = user = get_user_model().objects.create_user(
            username=f"user_{handle}",
            email=f"{handle}@localhost",
            password="test",
        )

        self.api_key = user.key_set.first()

        personal_org = user.personal_org

        personal_org.name = f"PersonalOrg{handle}"
        personal_org.slug = f"personalorg{handle}"
        personal_org.save()

        self.org = org = Organization.objects.create(name=handle, slug=handle)
        org.add_user(user, perms="crud")

        self.org_branding = org_branding = OrganizationBranding.objects.create(
            org=self.org
        )

        admin_role, _ = Role.objects.get_or_create(
            name="admin",
            description="",
            level=15,
            auto_set_on_creator=True,
            auto_set_on_member=False,
        )

        OrganizationRole.objects.get_or_create(
            org=self.org, user=self.user, role=admin_role
        )

        org_managed_permission, _ = ManagedPermission.objects.get_or_create(
            namespace="org.{org_id}",
            description="",
            group="aaactl",
        )

        ManagedPermissionRoleAutoGrant.objects.get_or_create(
            managed_permission=org_managed_permission,
            role=admin_role,
            permissions=PERM_CRUD,
        )

        user_managed_permission = ManagedPermission.objects.create(
            namespace="user.{org_id}",
            description="",
            group="aaactl",
        )

        ManagedPermissionRoleAutoGrant.objects.get_or_create(
            managed_permission=user_managed_permission,
            role=admin_role,
            permissions=PERM_CRUD,
        )

        billing_managed_permission = ManagedPermission.objects.create(
            namespace="billing.{org_id}",
            description="",
            group="aaactl",
        )

        ManagedPermissionRoleAutoGrant.objects.get_or_create(
            managed_permission=billing_managed_permission,
            role=admin_role,
            permissions=PERM_CRUD,
        )

        service_bridge_managed_permission = ManagedPermission.objects.create(
            namespace="service_bridge.*",
            description="",
            group="aaactl",
        )

        ManagedPermissionRoleAutoGrant.objects.get_or_create(
            managed_permission=service_bridge_managed_permission,
            role=admin_role,
            permissions=PERM_CRUD,
        )
        
        ManagedPermission.apply_roles_all()

        self.other_org = Organization.objects.create(
            name=f"Other {handle}", slug=f"other-{handle}"
        )

        self.user_unpermissioned = (
            user_unpermissioned
        ) = get_user_model().objects.create_user(
            username=f"user_{handle}_unperm",
            email=f"{handle}_unperm@localhost",
            password="test",
        )

        org.add_user(user_unpermissioned, perms="r")

        self.api_client = APIClient()
        self.api_client.login(username=user.username, password="test")

        self.api_client_unperm = APIClient()
        self.api_client_unperm.login(
            username=user_unpermissioned.username, password="test"
        )

        self.api_client_anon = APIClient()

        self.client = Client()
        self.client.login(username=user.username, password="test")

        self.client_anon = Client()

        self.perms = Permissions(user)


def make_account_objects(handle="test"):
    return AccountObjects(handle)


def make_billing_objects():
    return BillingObjects()


@pytest.fixture
def client_anon():
    return Client()


@pytest.fixture
def api_client_anon():
    from rest_framework.test import APIClient

    return APIClient()


@pytest.fixture
def account_objects():
    return make_account_objects()


@pytest.fixture
def billing_objects():
    return make_billing_objects()


@pytest.fixture
def billing_objects_w_pay(billing_objects):
    # add product to monthly subscription

    billing_objects.monthly_subscription.add_product(
        billing_objects.product_subscription_fixed
    )

    # add payment method to monthly subscription

    billing_objects.monthly_subscription.payment_method = billing_objects.payment_method
    billing_objects.monthly_subscription.save()

    return billing_objects


@pytest.fixture
def account_objects_b():
    return make_account_objects("test_b")


@pytest.fixture
def charge_objects(billing_objects, mocker):
    from datetime import datetime, timedelta, timezone

    from billing.models import OrderHistory, SubscriptionCycleProduct

    mocker.patch(
        "billing.payment_processors.stripe.stripe.Charge.create",
        return_value={"id": 1234, "receipt_url": "https://example.com"},
    )
    subscription = billing_objects.monthly_subscription

    product_fixed = billing_objects.product_subscription_fixed
    subscription.add_product(product_fixed)
    fixed_subscription_product = product_fixed.subscription_set.first()

    subscription.payment_method = billing_objects.payment_method
    two_weeks_ago = (datetime.now(timezone.utc) - timedelta(days=14)).date()
    subscription.start_subscription_cycle(two_weeks_ago)
    subscription_cycle = subscription.subscription_cycle_set.first()

    SubscriptionCycleProduct.objects.create(
        subscription_cycle=subscription_cycle,
        subscription_product=fixed_subscription_product,
        usage=1,
    )

    subscription_cycle.charge()

    subscription_cycle_charge = subscription_cycle.subscription_cycle_charge_set.first()
    payment_charge = subscription_cycle_charge.payment_charge

    order_history = OrderHistory.create_from_payment_charge(payment_charge)

    return {
        "subscription": subscription,
        "subscription_cycle": subscription_cycle,
        "subscription_cycle_charge": subscription_cycle_charge,
        "payment_charge": payment_charge,
        "order_history": order_history,
    }


def create_transaction_data(billing_objects):
    return {
        "amount": 1200.99,
    }


def create_money_transaction_data(billing_objects):
    return {
        "amount": 1200.99,
        "billing_contact": billing_objects.billing_contact,
        "payment_method": billing_objects.payment_method,
    }


@pytest.fixture
def order(billing_objects):
    from billing.models import Order, OrderLine

    data = create_transaction_data(billing_objects)
    data.update(
        {
            "product": billing_objects.product,
            "description": "This product is helpful",
        }
    )

    order = Order.objects.create(org=billing_objects.org, order_number=132)
    order_line = OrderLine.objects.create(order=order, **data)
    return order_line


@pytest.fixture
def invoice(billing_objects, order):
    from billing.models import Invoice, InvoiceLine, Order

    data = create_transaction_data(billing_objects)
    data.update(
        {
            "subscription": billing_objects.monthly_subscription,
            "description": "This subscription is helpful",
        }
    )
    order = Order.objects.create(org=billing_objects.org, order_number=132)
    invoice = Invoice.objects.create(
        order=order, invoice_number=312, org=billing_objects.org
    )
    invoice_line = InvoiceLine.objects.create(invoice=invoice, **data)
    return invoice_line


@pytest.fixture
def payment(billing_objects):
    from billing.models import Payment

    data = create_money_transaction_data(billing_objects)
    data.update({"invoice_number": 1231, "org": billing_objects.org})
    payment = Payment.objects.create(**data)
    return payment


@pytest.fixture
def deposit(billing_objects):
    from billing.models import Deposit

    data = create_money_transaction_data(billing_objects)
    deposit = Deposit.objects.create(org=billing_objects.org, **data)
    return deposit


@pytest.fixture
def withdrawal(billing_objects):
    from billing.models import Withdrawal

    data = create_money_transaction_data(billing_objects)
    withdrawal = Withdrawal.objects.create(org=billing_objects.org, **data)
    return withdrawal


@pytest.fixture
def ledger(withdrawal, order, invoice):
    return [withdrawal, order, invoice]
