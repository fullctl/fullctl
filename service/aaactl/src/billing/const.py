from django.utils.translation import gettext as _

BILLING_CYCLE_CHOICES = (("month", _("Monthly")), ("year", _("Yearly")))

BILLING_MODIFIER_TYPES = (
    ("reduction", _("Price Reduction")),
    ("reduction_p", _("Price Reduction (%)")),
    ("quantity", _("Free Quantity")),
    ("free", _("Free")),
)

BILLING_PRODUCT_RECURRING_TYPES = (
    ("fixed", _("Fixed Price")),
    ("metered", _("Metered Unit Price")),
)

CURRENCY_TYPES = (("USD", _("USD")),)
