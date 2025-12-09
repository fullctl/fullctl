class BillingError(ValueError):
    pass


class OrgProductAlreadyExists(BillingError):
    pass
