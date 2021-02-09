from django.core.exceptions import ObjectDoesNotExist

from fullctl.django.inet.exceptions import PdbNotFoundError


def pdb_lookup(cls, **filters):
    try:
        return cls.objects.get(**filters)
    except ObjectDoesNotExist:
        raise PdbNotFoundError(cls.handleref.tag, filters)
