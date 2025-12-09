from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from fullctl.django import auditlog

from billing.models import (
    Deposit,
    InvoiceLine,
    Ledger,
    OrderLine,
    OrganizationProduct,
    OrganizationProductHistory,
    Payment,
    SubscriptionProduct,
    Withdrawal,
)


@receiver(post_save, sender=OrganizationProduct)
def handle_orgproduct_save(sender, **kwargs):
    """
    When a organization is granted access to a product
    through OrganizationProduct ensure any permissions
    granted through the product become managable by
    the organization
    """

    org_product = kwargs.get("instance")

    for managed_permission_grant in org_product.product.managed_permissions.all():
        managed_permission_grant.apply(org_product)

    if kwargs.get("created"):
        with auditlog.Context() as log:
            log.set("org", org_product.org)
            log.log("product_added_to_org", log_object=org_product.product)

        org_product.add_to_history()


@receiver(post_delete, sender=OrganizationProduct)
def handle_orgproduct_delete(sender, **kwargs):
    """
    Create audit log entry `product_removed_from_org` when OrganizationProduct
    instance is deleted
    """

    org_product = kwargs.get("instance")

    with auditlog.Context() as log:
        log.set("org", org_product.org)
        log.log("product_removed_from_org", log_object=org_product.product)


@receiver(post_save, sender=SubscriptionProduct)
def handle_subscription_product_save(sender, **kwargs):
    """
    When a product is added to a subscription also create
    the necessary OrganizationProduct instances
    """

    if not kwargs.get("created"):
        return

    sub_product = kwargs.get("instance")

    component_object_id = sub_product.component_object_id
    component_object_name = sub_product.component_object_name
    sub_product.update_expires()

    OrganizationProduct.objects.get_or_create(
        subscription=sub_product.subscription,
        subscription_product=sub_product,
        product=sub_product.product,
        org=sub_product.subscription.org,
        component_object_id=component_object_id,
        component_object_name=component_object_name,
        expires=sub_product.expires,
    )

    if sub_product.subscription.subscription_cycle:
        sub_product.subscription.subscription_cycle.add_subscription_product(
            sub_product
        )


@receiver(post_delete, sender=SubscriptionProduct)
def handle_subscription_product_delete(sender, **kwargs):
    """
    When a product is removed from a subscription also remove
    the OrganizationProduct for it if it exists.
    """

    sub_product = kwargs.get("instance")

    qset = OrganizationProduct.objects.filter(
        subscription=sub_product.subscription,
        subscription_product=sub_product,
        product=sub_product.product,
    )

    for org_product in qset:
        org_product.delete()


for TransactionModel in [InvoiceLine, OrderLine, Payment, Deposit, Withdrawal]:

    @receiver(post_save, sender=TransactionModel)
    def handle_billing_object_save(sender, **kwargs):
        created = kwargs.get("created")
        if not created:
            return
        txn = kwargs.get("instance")
        Ledger.objects.create(
            content_object=txn,
            invoice_number=getattr(txn, "invoice_number", None),
            order_number=getattr(txn, "order_number", None),
            org=txn.org,
        )
