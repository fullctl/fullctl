from django.db.models import CharField
from django.db.models.functions import Lower
from rest_framework.filters import OrderingFilter


class CaseInsensitiveOrderingFilter(OrderingFilter):
    def __init__(self, ordering_fields):
        self.ordering_fields = ordering_fields

    def _handle_field(self, name, queryset):
        # Since we got name from self.get_ordering() we are
        # assuming the field name is valid

        field = queryset.model._meta.get_field(name.replace("-", ""))

        # For CharacterFields, use case insensitive ordering
        if isinstance(field, CharField):
            if name.startswith("-"):
                return Lower(field.name).desc()
            else:
                return Lower(field.name)
        return name

    def filter_queryset(self, request, queryset, view):
        _ordering = self.get_ordering(request, queryset, view)

        ordering = []

        if _ordering:
            for name in _ordering:
                ordering.append(self._handle_field(name, queryset))

        return queryset.order_by(*ordering)
