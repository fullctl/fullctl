import reversion
from django.db.models import ProtectedError
from fullctl.django.auditlog import auditlog
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

import applications.models as application_models
import billing.models as models
from account.rest.decorators import set_org
from billing.rest.route import route
from billing.rest.serializers import Serializers
from common.rest.decorators import grainy_endpoint


@route
class Organization(viewsets.ViewSet):
    ref_tag = "org"

    @set_org
    @grainy_endpoint("billing.{org.id}", explicit=False)
    def retrieve(self, request, pk, org):
        return Response({})

    @action(detail=True, methods=["POST"])
    @set_org
    @auditlog()
    @grainy_endpoint("billing.{org.id}", explicit=False)
    def billing_setup(self, request, pk, org, auditlog=None):
        reversion.set_user(request.user)

        serializer = Serializers.setup(
            data=request.data,
            many=False,
            context={"user": request.user, "org": org, "data": request.data},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)
        serializer.save()
        return Response(serializer.data)

    @action(detail=True, methods=["GET"])
    @set_org
    @grainy_endpoint("billing.{org.id}", explicit=False)
    def payment_methods(self, request, pk, org):
        billing_contact = request.GET.get("billing_contact")

        if not billing_contact:
            return Response({"billing_contact": ["Required field"]}, status=400)

        queryset = (
            models.PaymentMethod.get_for_org(org, status=None)
            .filter(billing_contact_id=billing_contact)
            .order_by("-updated")
        )
        print(queryset.all(), org)
        serializer = Serializers.payment_method(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["DELETE"])
    @set_org
    @auditlog()
    @grainy_endpoint("billing.{org.id}", explicit=False)
    def payment_method(self, request, pk, org, auditlog=None):
        payment_method = models.PaymentMethod.objects.get(
            billing_contact__org=org, id=request.data.get("id")
        )

        if (
            payment_method.billing_contact.payment_method_set.filter(
                status="ok"
            ).count()
            <= 1
        ):
            return Response(
                {
                    "non_field_errors": [
                        "Need at least one payment method set on a billing contact. Delete the billing contact itself if it is no longer needed"
                    ]
                },
                status=400,
            )

        old_id = payment_method.id
        models.Subscription.set_payment_method(org, replace=payment_method)
        payment_method.delete()
        payment_method.id = old_id
        serializer = Serializers.payment_method(payment_method, many=False)

        return Response(serializer.data)

    @action(detail=True, methods=["PUT", "DELETE"])
    @set_org
    @auditlog()
    @grainy_endpoint("billing.{org.id}", explicit=False)
    def billing_contact(self, request, pk, org, auditlog=None):
        instance = org.billing_contact_set.get(id=request.data.get("id"))

        if request.method == "PUT":
            serializer = Serializers.billing_contact(
                instance=instance,
                data=request.data,
            )

            if not serializer.is_valid():
                return Response(serializer.errors, status=400)
            serializer.save()

        elif request.method == "DELETE":
            serializer = Serializers.billing_contact(instance=instance)
            instance.delete()
            models.Subscription.set_payment_method(org)

        return Response(serializer.data)

    @action(detail=True, methods=["GET"])
    @set_org
    @grainy_endpoint("billing.{org.id}", explicit=False)
    def services(self, request, pk, org):
        queryset = models.Subscription.objects.filter(org=org)
        serializer = Serializers.subscription(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["POST"])
    @set_org
    @auditlog()
    @grainy_endpoint("billing.{org.id}", explicit=False)
    def subscribe(self, request, pk, org, auditlog=None):
        name = request.data.get("product")

        try:
            product = models.Product.objects.get(name=name)
        except models.Product.DoesNotExist:
            return Response({"product": [f"Unknown product: {name}"]}, status=400)

        subscription = models.Subscription.get_or_create(org, product.group)
        subscription.add_product(product)
        if not subscription.subscription_cycle:
            subscription.start_subscription_cycle()

        serializer = Serializers.subscription(subscription)
        return Response(serializer.data)

    @action(detail=True, methods=["POST"])
    @set_org
    @auditlog()
    @grainy_endpoint("billing.{org.id}", explicit=False)
    def start_trial(self, request, pk, org, auditlog=None):
        service_id = request.data.get("service_id")
        component_object_id = request.data.get("component_object_id")
        service = application_models.Service.objects.get(id=service_id)

        print("Attempting to start trial", service_id, component_object_id)

        if not service.trial_product_id:
            return Response({"service_id": ["This service has no trial"]}, status=400)

        if not service.trial_product.can_add_to_org(
            org, component_object_id=component_object_id
        ):
            return Response(
                {"non_field_errors": ["Trial could not be started at this time"]},
                status=400,
            )

        org_product = service.trial_product.add_to_org(
            org,
            component_object_id=component_object_id,
            notes="Trial started through service bridge",
        )

        serializer = Serializers.org_product(org_product)
        return Response(serializer.data)

    @action(detail=True, methods=["GET"])
    @set_org
    @grainy_endpoint("billing.{org.id}", explicit=False)
    def orders(self, request, pk, org):
        queryset = models.OrderHistory.objects.filter(billing_contact__org=org)
        queryset = queryset.prefetch_related("order_history_item_set").select_related(
            "billing_contact"
        )
        queryset = queryset.order_by("-processed")
        serializer = Serializers.order_history(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=["GET"])
    @set_org
    @grainy_endpoint("billing.{org.id}", explicit=False)
    def open_invoices(self, request, pk, org):
        queryset = models.Invoice.objects.filter(org=org)
        queryset = queryset.order_by("-created")[:25]

        instances = [invoice for invoice in queryset if not invoice.paid]

        serializer = Serializers.invoice(instances, many=True)
        return Response(serializer.data)


@route
class Product(viewsets.ViewSet):
    serializer_class = Serializers.product
    queryset = models.Product.objects.all()

    def list(self, request):
        queryset = models.Product.objects.filter(status="ok")
        serializer = Serializers.product(queryset, many=True)
        return Response(serializer.data)
