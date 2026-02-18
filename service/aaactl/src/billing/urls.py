from django.urls import path

import billing.stripe_views as stripe_views
import billing.views

urlpatterns = [
    # path("setup/test/", billing.views.setup_test, name="setup-test"),
    path("setup/", billing.views.setup, name="setup"),
    path("services/", billing.views.services, name="services"),
    path(
        "billing-contacts/<int:id>/",
        billing.views.billing_contact,
        name="billing-contact",
    ),
    path("billing-contacts/", billing.views.billing_contacts, name="billing-contacts"),
    path(
        "order-history/details/<str:id>/",
        billing.views.order_history_details,
        name="order-history-details",
    ),
    path("order-history/", billing.views.order_history, name="order-history"),
    path(
        "create-setup-intent/",
        stripe_views.create_setup_intent,
        name="create_setup_intent",
    ),
    path(
        "check-setup-intent/<str:id>/",
        stripe_views.check_setup_intent,
        name="check_setup_intent",
    ),
    path(
        "save-payment-method/<int:payment_method_id>/",
        stripe_views.save_payment_method,
        name="save_payment_method",
    ),
]
