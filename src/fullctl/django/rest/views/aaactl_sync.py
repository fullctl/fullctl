"""
API views to facilitate data synchronization from aaactl to the fullctl
service.

These views require permissions to the `aaactl_sync` namespace which usually
only exists on the internal api key used for service bridging
"""

import datetime

from django.contrib.auth import get_user_model

from rest_framework import viewsets
from rest_framework.response import Response
from rest_framework.decorators import action

import fullctl.django.models as models
from fullctl.django.rest.decorators import grainy_endpoint
from fullctl.django.rest.mixins import CachedObjectMixin, OrgQuerysetMixin
from fullctl.django.rest.route.aaactl_sync import route
from fullctl.django.rest.serializers.aaactl_sync import Serializers

@route
class User(CachedObjectMixin, viewsets.GenericViewSet):

    """
    Sync user information from aaactl using the service bridge

    - username
    - email
    - first name
    - last name
    """

    serializer_class = Serializers.user
    queryset = get_user_model().objects.all()

    # this approach assumes that aaactl is the only authentication
    # provider
    lookup_field = "social_auth__uid"
    lookup_url_kwarg = "remote_id"

    @grainy_endpoint("aaactl_sync.user")
    def update(self, request, username, *args, **kwargs):
        user = self.get_object()
        serializer = self.serializer_class(instance=user, data=request.data)
        return Response(serializer.data)


@route
class Organization(CachedObjectMixin, viewsets.GenericViewSet):

    """
    Sync organization information from aaactl using the service
    brdige

    - name
    - url slug
    """

    serializer_class = Serializers.org
    queryset = models.Organization.objects.all()
    lookup_field = "remote_id"
    lookup_url_kwarg = "remote_id"

    @grainy_endpoint("aaactl_sync.org")
    def update(self, request, remote_id, *args, **kwargs):
        org = self.get_object()
        serializer = self.serializer_class(instance=org, data=request.data)
        return Response(serializer.data)


@route
class OrganizationUser(CachedObjectMixin, viewsets.GenericViewSet):

    """
    Sync organization<->user relationships from aaactl using the service
    bridge
    """

    serializer_class = Serializers.orguser
    queryset = models.OrganizationUser.objects.all()

    lookup_field = "org__remote_id"
    lookup_url_kwarg = "org_remote_id"

    @grainy_endpoint("aaactl_sync.orguser")
    def create(self, request, pk, *args, **kwargs):
        org = self.get_object()

        #serializer = self.serializer_class(instance=user, data=request.data)
        #return Response(serializer.data)


    @grainy_endpoint("aaactl_sync.orguser")
    def destroy(self, request, pk, *args, **kwargs):
        org = self.get_object()



