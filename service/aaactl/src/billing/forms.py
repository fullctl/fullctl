from django import forms
from django.core.exceptions import ObjectDoesNotExist
from django.core.validators import EmailValidator
from django.utils.translation import gettext as _
from phonenumber_field.formfields import PhoneNumberField
from phonenumber_field.widgets import PhoneNumberPrefixWidget

import billing.payment_processors
from billing.models import PaymentMethod, Product


class BillingSetupInitForm(forms.Form):
    product = forms.CharField(widget=forms.HiddenInput(), required=False)
    subscription_cycle = forms.CharField(widget=forms.HiddenInput(), required=False)
    redirect = forms.CharField(widget=forms.HiddenInput(), required=False)

    def clean(self):
        cleaned_data = super().clean()
        product_name = cleaned_data.get("product")

        try:
            product = Product.objects.get(name=product_name)
        except Product.DoesNotExist:
            raise forms.ValidationError(_("Unknown product: {}").format(product_name))

        self.product_instance = product

        try:
            self.recurring_product_instance = product.recurring_product
        except ObjectDoesNotExist:
            self.recurring_product_instance = None

        return cleaned_data


class SelectPaymentMethodForm(forms.Form):
    payment_method = forms.ModelChoiceField(
        queryset=PaymentMethod.objects.all(),
        required=False,
        label=_("Saved payment method"),
    )

    def __init__(self, org, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["payment_method"].queryset = PaymentMethod.get_for_org(org)


class CreatePaymentMethodForm(forms.Form):
    processor = forms.ChoiceField(
        choices=billing.payment_processors.choices(), widget=forms.HiddenInput()
    )


class BillingContactDetails(forms.Form):
    holder = forms.CharField(label=_("Full Name"), required=True)
    email = forms.EmailField(label=_("Email Address"), required=True)
    phone_number = PhoneNumberField(
        label=_("Phone Number"),
        widget=PhoneNumberPrefixWidget(
            initial="US", attrs={"class": "form-control w-auto d-inline-block"}
        ),
    )


class BillingAgreementsForm(forms.Form):
    agreement_tos = forms.BooleanField(label=_("I agree to the Terms of Service"))


class BillingContactForm(forms.Form):
    name = forms.CharField(
        label=_("Name"), widget=forms.TextInput(attrs={"readonly": True})
    )
    email = forms.EmailField(label=_("Email Address"))
    phone_number = PhoneNumberField(
        label=_("Phone Number"),
        widget=PhoneNumberPrefixWidget(
            initial="US", attrs={"class": "form-control w-auto d-inline-block"}
        ),
    )
