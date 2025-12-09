import dataclasses
import traceback

import reversion
from django.core.management.base import CommandError
from django.db.models import QuerySet
from django.utils import timezone
from fullctl.django.auditlog import auditlog
from fullctl.django.management.commands.base import CommandInterface

from billing.models import Invoice, OrganizationProduct, Subscription, SubscriptionCycle
from billing.payment_processors.processor import InternalProcessorError


@dataclasses.dataclass
class InternalErrorInfo:
    subscription_cycle: SubscriptionCycle
    exc: Exception
    traceback: str


def catch_internal_processor_error(fn):
    """
    decorator to catch internal processor errors and log them
    """

    def wrapper(self, *args, **kwargs):
        try:
            return fn(self, *args, **kwargs)
        except InternalProcessorError as exc:
            self.log_error(f"\n\n---- INTERNAL PROCESSING ERROR\n\n{exc}\n\n----\n\n")

    return wrapper


class Command(CommandInterface):
    help = "Progresses billing subscription cycles and product expiry"

    commit = False

    def add_arguments(self, parser):
        super().add_arguments(parser)

        parser.add_argument(
            "--group",
            "-g",
            dest="group",
            metavar="GROUP",
            type=str,
            required=False,
            help=(
                "Limit processing to a single ProductGroup. "
                "Accepts either the numeric ID or the name of the group."
            ),
        )

    def handle(self, *args, **kwargs):
        # Extract optional group filter so that it can be used by helper methods
        self.group_filter = kwargs.get("group")

        self.critical_cycle_errors = []

        super().handle(*args, **kwargs)

        self.handle_cycle_errors(self.critical_cycle_errors)

    def run(self, *args, **kwargs):
        self.progress_product_expiry()
        self.progress_subscription_cycles()
        self.sync_open_invoices()

    def progress_product_expiry(self, *args, **kwargs):
        qset = OrganizationProduct.objects.filter(expires__lt=timezone.now())

        # Apply --group filter if provided
        if getattr(self, "group_filter", None):
            qset = self._filter_by_group(qset, "product__group")

        for org_prod in qset:
            self.log_info(f"Expiring {org_prod.product} for {org_prod.org}")
            if org_prod.product.expiry_replacement_product_id:
                replacement_product = org_prod.product.expiry_replacement_product
            else:
                replacement_product = None

            org_prod.delete()

            if replacement_product and replacement_product.can_add_to_org(org_prod.org):
                self.log_info(
                    f"Replacing expired product with {replacement_product} for {org_prod.org}"
                )
                replacement_product.add_to_org(org_prod.org)

    def progress_subscription_product_expiry(self, subscription):
        qset = subscription.subscription_product_set.filter(expires__lt=timezone.now())
        for subscription_product in qset:
            self.log_info(
                f"Expiring {subscription_product.product} from subscription {subscription}"
            )
            if subscription_product.product.expiry_replacement_product_id:
                replacement_product = (
                    subscription_product.product.expiry_replacement_product
                )
                if replacement_product and replacement_product.can_add_to_org(
                    subscription.org
                ):
                    self.log_info(
                        f"Replacing expired product with {replacement_product} in subscription {subscription}"
                    )
                    replacement_product.add_to_org(subscription.org)

    @catch_internal_processor_error
    def progress_subscription_cycles(self):
        # Base queryset: active subscriptions only
        qset = Subscription.objects.filter(status="ok")

        # Apply --group filter if provided
        if getattr(self, "group_filter", None):
            qset = self._filter_by_group(qset, "group")

        errored = self.critical_cycle_errors

        for subscription in qset:
            self.log_info(
                f"checking subscription {subscription} ({subscription.id}) ..."
            )

            if not subscription.subscription_cycle:
                subscription.start_subscription_cycle()
                self.log_info(
                    f"-- started new billing subscription_cycle: {subscription.subscription_cycle}"
                )
            else:
                self.log_info(
                    f"-- subscription_cycle: {subscription.subscription_cycle}"
                )

            for subscription_product in subscription.subscription_product_set.all():
                self.collect(subscription_product, subscription.subscription_cycle)

            if subscription.billing_paused:
                self.log_info(
                    f"-- billing paused, unpaid cycles will not be charged"
                )
                continue


            for subscription_cycle in subscription.subscription_cycle_set.filter(
                status__in=["open", "failed"]
            ):
                if not subscription_cycle.ended and subscription.charge_type == "end":
                    continue
                if not subscription.payment_method_id:
                    Subscription.set_payment_method(subscription.org)
                if not subscription.payment_method_id:
                    self.log_info(
                        f"-- no payment method set, unable to charge subscription cycle for org {subscription.org}"
                    )
                    break

                if not subscription_cycle.charged:
                    if subscription_cycle.status == "failed":
                        # we are retrying a failed subscription cycle charge

                        self.log_info("-- retrying failed subscription cycle charge")

                    self.log_info(
                        f"-- charging ${subscription_cycle.price} for subscription cycle: {subscription_cycle}"
                    )

                    try:
                        with reversion.create_revision():
                            subscription_cycle_charge = subscription_cycle.charge(
                                commit=self.commit
                            )

                        with reversion.create_revision():
                            if subscription_cycle_charge:
                                subscription_cycle_charge.payment_charge.sync_status(
                                    commit=self.commit
                                )
                    except InternalProcessorError:
                        # Errors like legacy payment methods, etc. that are handled
                        # separately and don't lead to any actual charges made
                        raise
                    except Exception as exc:
                        # DATABASE/DJANGO error where the charge may have been made
                        #
                        # subscription cycle will be set to `error` and manual
                        # review wil be required.
                        #
                        # A proper error will be raised at the end of command
                        # execution containing all errored subscriptions.
                        #
                        # Subscription cycles with status `error` will not be retried
                        # and will require manual review.
                        error_info = InternalErrorInfo(
                            subscription_cycle=subscription_cycle,
                            exc=exc,
                            traceback=traceback.format_exc(),
                        )
                        errored.append(error_info)
                        self.log_error(
                            f"INTERNAL ERROR (possibly charged)\n{error_info}"
                        )
                        subscription_cycle.status = "error"
                        subscription_cycle.save(update_fields=["status"])

            # sync charge processing status

            for subscription_cycle in subscription.subscription_cycle_set.filter(
                subscription_cycle_charge_set__payment_charge__status__in=["pending"]
            ).distinct("id"):
                subscription_cycle_charges = (
                    subscription_cycle.subscription_cycle_charge_set.filter(
                        payment_charge__status="pending"
                    )
                )
                for subscription_cycle_charge in subscription_cycle_charges:
                    self.log_info(
                        f"-- syncing pending subscription cycle charge: {subscription_cycle_charge}"
                    )
                    subscription_cycle_charge.payment_charge.sync_status(
                        commit=self.commit
                    )

    def handle_cycle_errors(self, errored):
        if not errored:
            return

        subscriptions = []

        for error_info in errored:
            if self.commit:
                error_info.subscription_cycle.set_error(error_info.traceback)
            subscriptions.append(error_info.subscription_cycle.subscription)

        raise CommandError(
            f"Critical errors occurred in {len(subscriptions)} subscriptions: \n\n{subscriptions}\n\nPlease review manually."
        )

    def collect(self, subscription_product, subscription_cycle):
        org = subscription_cycle.subscription.org

        service = subscription_product.product.component
        if not service:
            subscription_cycle.update_usage(subscription_product, None)
            return
        bridge = service.bridge(org)
        product = subscription_product.product.name

        try:
            usage = bridge.usage(product)
            self.log_info(f"{org} -> {product}: {usage}")
            subscription_cycle.update_usage(subscription_product, usage)
        except KeyError as exc:
            self.log_error(f"{exc}")

    def sync_open_invoices(self):
        qset = Invoice.objects.filter(status="pending").order_by("created")

        for invoice in qset:
            if not invoice.data.get("stripe_invoice"):
                continue

            self.log_info(f"syncing open invoice {invoice}")
            invoice.sync_status(commit=self.commit)

    def _filter_by_group(self, queryset:QuerySet, lookup_prefix:str) -> QuerySet:
        """
        Return the queryset filtered down to the selected ProductGroup.

        The lookup_prefix argument is the relation path to the ProductGroup field
        on the supplied queryset model. 
        
        For instance:
            * "group" for Subscription
            * "product__group" for OrganizationProduct
        """
        group_value = getattr(self, "group_filter", None)
        if not group_value:
            return queryset

        # Try to interpret the value as an integer primary key first; if that
        # fails (ValueError) or results in no match we fall back to filtering by
        # group name. This makes the option flexible for both CI scripts (which
        # often prefer ids) and humans (who prefer names).
        try:
            group_id = int(group_value)
            criteria = {f"{lookup_prefix}__id": group_id}
            qs = queryset.filter(**criteria)
            if qs.exists():
                return qs
        except (ValueError, TypeError):
            # Not an int – interpret as name
            pass

        criteria = {f"{lookup_prefix}__name": group_value}
        return queryset.filter(**criteria)
