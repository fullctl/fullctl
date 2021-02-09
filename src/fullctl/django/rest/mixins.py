class CachedObjectMixin:

    """
    Assures that a views get_object() call only
    queries the db once
    """

    def get_object(self):
        if getattr(self, "_obj", None) is None:
            self._obj = super().get_object()

        return self._obj


class OrgQuerysetMixin:
    """
    For objects with URLs that require an "org_tag", this filters
    the resulting queryset by matching the instance org to the
    provided slug.
    """

    def get_queryset(self):
        org_tag = self.kwargs["org_tag"]
        return self.queryset.filter(instance__org__slug=org_tag)
