from fullctl.django.inet.exceptions import PdbNotFoundError
from django.core.exceptions import ObjectDoesNotExist


def pdb_lookup(cls, **filters):
    try:
        return cls.objects.get(**filters)
    except ObjectDoesNotExist:
        raise PdbNotFoundError(cls.handleref.tag, filters)
