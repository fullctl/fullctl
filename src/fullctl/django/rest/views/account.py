from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

import fullctl.django.models as models
from fullctl.django.rest.decorators import grainy_endpoint
from fullctl.django.rest.route.account import route
from fullctl.django.rest.serializers.account import Serializers
from fullctl.django.util import verified_asns


@route
class Organization(viewsets.GenericViewSet):

    """
    Manage user's organizations
    """

    serializer_class = Serializers.org
    queryset = models.Organization.objects.all()

    def list(self, request, *args, **kwargs):

        """
        list the organizations that the user belongs
        to or has permissions to
        """

        serializer = Serializers.org(
            instance=models.Organization.accessible(request.user),
            many=True,
            context={"user": request.user},
        )
        return Response(serializer.data)


@route
class User(viewsets.GenericViewSet):

    ref_tag = "user"
    serializer_class = Serializers.asn

    @action(detail=False, methods=["GET"])
    @grainy_endpoint()
    def asns(self, request, org, *args, **kwargs):
        serializer = Serializers.asn(verified_asns(request.perms), many=True)
        return Response(serializer.data)
