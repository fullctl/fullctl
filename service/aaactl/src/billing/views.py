from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.utils.translation import gettext as _

from account.decorators import org_view
from account.forms import ChangeInformation
from billing.forms import (
    BillingAgreementsForm,
    BillingContactDetails,
    BillingContactForm,
    BillingSetupInitForm,
    SelectPaymentMethodForm,
)
from billing.models import BillingContact, OrderHistory, PaymentMethod
from billing.payment_processors import PROCESSORS

# Create your views here.


@login_required
@org_view(["billing", "orderhistory"])
def order_history(request):
    order_history = OrderHistory.objects.filter(
        billing_contact__org=request.selected_org
    )
    order_history = order_history.order_by("-processed")
    env = dict(order_history=order_history, form=ChangeInformation(None))
    return render(request, "billing/controlpanel/order_history.html", env)


@login_required
@org_view(["billing", "orderhistory"])
def order_history_details(request, id):
    user = request.user
    form = ChangeInformation(
        user,
        initial={
            "username": user.username,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
        },
    )
    try:
        order_history = OrderHistory.objects.get(
            billing_contact__org=request.selected_org, order_id=id
        )
    except OrderHistory.DoesNotExist:
        raise Http404(_("Order history not found"))

    env = dict(order_history=order_history, form=form)
    return render(request, "billing/controlpanel/order_history_details.html", env)


@login_required
@org_view(["billing", "contact"])
def billing_contacts(request):
    billing_contacts = request.selected_org.billing_contact_set.filter(status="ok")
    env = dict(billing_contacts=billing_contacts)
    return render(request, "billing/controlpanel/billing_contacts.html", env)


@login_required
@org_view(["billing", "contact"])
def billing_contact(request, id):
    try:
        billing_contact = request.selected_org.billing_contact_set.get(id=id)
    except request.user.payment_method_set.model.DoesNotExist:
        raise Http404(_("Billing contact not found"))

    env = dict(
        billing_contact=billing_contact,
        form=BillingContactForm(
            initial={
                "name": billing_contact.name,
                "email": billing_contact.email,
                "phone_number": billing_contact.phone_number,
            }
        ),
    )
    return render(request, "billing/controlpanel/billing_contact.html", env)


@login_required
@org_view(["billing", "service"])
def services(request):
    billing_is_setup = PaymentMethod.objects.filter(
        billing_contact__org=request.selected_org, status="ok"
    ).exists()

    services = request.selected_org.subscription_set.filter(status="ok")
    env = dict(
        services=services,
        billing_is_setup=billing_is_setup,
        form=ChangeInformation(None),
    )
    return render(request, "billing/controlpanel/services.html", env)


"""
@login_required
@org_view(["billing", "contact"])
def setup_test(request):

    # we are initializing with test data to speed up
    # development, this part should be removed once
    # implementation is complete

    test_init = {
        "redirect": "https://dev2.20c.com:8041/.../prefix",
        "product": "fullctl.prefixctl.prefixes",
        "email": request.user.email,
        "test_charge": True,
    }

    return setup(request, test_init=test_init)
"""


@login_required
@org_view(["billing", "contact"])
def setup(request, **kwargs):
    test_init = kwargs.get("test_init")
    real_init = {"email": request.user.email, "product": request.GET.get("product")}
    billing_address_init = {}

    env = {}
    org = request.selected_org

    # If `billing_contact` parameter is specified attempt
    # to load existing billing contact and prefill
    # the name and email fields from it

    billing_contact = request.GET.get("billing_contact")
    if billing_contact:
        try:
            billing_contact = BillingContact.objects.get(id=billing_contact, org=org)
            billing_address_init.update(
                holder=billing_contact.name,
                email=billing_contact.email,
                phone_number=billing_contact.phone_number,
            )
        except BillingContact.DoesNotExist:
            pass

    # Initializion form

    if test_init:
        form_init = BillingSetupInitForm(test_init, initial=test_init)
    elif request.GET.get("product"):
        form_init = BillingSetupInitForm(request.GET, initial=real_init)
    else:
        form_init = None

    if form_init:
        if not form_init.is_valid():
            # something wrong with initializing configuration

            messages.error(request, form_init.errors.as_ul())
            return render(request, "billing/setup-error.html", env)

        env.update(
            form_init=form_init,
            product=form_init.product_instance,
            recurring_product=form_init.recurring_product_instance,
            test_init=test_init,
        )

    # if the user already has a payment method set up make it
    # available for selection

    payopt = PaymentMethod.get_for_org(org).first()
    if payopt and "product" in env:
        env.update(
            form_payopt_select=SelectPaymentMethodForm(
                org, initial={"payment_method": payopt.id}
            )
        )

    # initialize payment processor and forms to create new payment
    # method

    payment_processor_id = request.GET.get("processor", list(PROCESSORS.keys())[0])
    payment_processor = PROCESSORS[payment_processor_id]
    env.update(
        payment_processor=payment_processor(
            PaymentMethod(billing_contact=BillingContact())
        ),
        form_payopt_create=payment_processor.Form(),
        from_payopt_create_template=payment_processor.Form().template,
        form_billing_address=BillingContactDetails(initial=billing_address_init),
        form_agreements=BillingAgreementsForm(),
    )

    return render(request, "billing/setup.html", env)
