from django.http import Http404

from fullctl.django.auth import permissions
from fullctl.django.models import Organization


class RequestAugmentation:

    """
    Augments the request by selecting org from `org_tag`
    passed in the URL

    When fullctl is not managed by oauth it also makes sure
    that the request users personal org exists.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        return response

    def process_view(self, request, view_func, view_args, view_kwargs):
        kwargs = request.resolver_match.kwargs
        request.perms = permissions(request.user)
        if (
            not hasattr(request.user, "org_set") or not request.user.org_set.exists()
        ) and "org_tag" not in kwargs:

            if not request.user.is_authenticated:

                # user is not authenticated, return
                # Guest org

                request.org = Organization(name="Guest")
                return

        try:
            if "org_tag" in kwargs:
                request.org = Organization.objects.get(slug=kwargs["org_tag"])

            elif request.user.org_set.exists():
                request.org = request.user.org_set.first().org

            if hasattr(request.user, "org_set"):
                request.orgs = request.user.org_set.all()
            else:
                request.orgs = []
        except Organization.DoesNotExist:
            raise Http404

        if not getattr(request, "org", None):
            request.org = Organization(name="Guest")

            return
