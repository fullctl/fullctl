import django_peeringdb.models.concrete as models
from django.db.models import Q

# from django.utils.translation import gettext_lazy as _
# from fullctl.django.rest.core import BadRequest
# from fullctl.django.rest.decorators import load_object
from fullctl.django.rest.route.service_bridge import route
from fullctl.django.rest.views.service_bridge import (
    DataViewSet,
    Exclude,
    HeartbeatViewSet,
    MethodFilter,
    StatusViewSet,
)

# from django_pdbctl.rest.decorators import grainy_endpoint
from django_pdbctl.rest.serializers.service_bridge import Serializers

# from rest_framework import viewsets
# from rest_framework.decorators import action
# from rest_framework.response import Response


@route
class Heartbeat(HeartbeatViewSet):
    pass


@route
class Status(StatusViewSet):
    checks = ("bridge_aaactl",)


@route
class InternetExchange(DataViewSet):
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("ids", "id__in"),
        ("org", "org_id"),
        ("q", "name__icontains"),
        ("ids", "id__in"),
        ("asn", MethodFilter("asn")),
    ]
    autocomplete = "name"
    allow_unfiltered = True

    queryset = models.InternetExchange.objects.filter(status="ok")
    serializer_class = Serializers.ix

    def filter_asn(self, qset, value):
        """
        Returns all exchanges that network specified by asn is peering at

        Arguments:

            qset - queryset
            value - asn
        """

        return qset.filter(ixlan_set__netixlan_set__asn=value).distinct("id")


@route
class Network(DataViewSet):
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("org", "org_id"),
        ("asn", "asn"),
        ("asns", "asn__in"),
        ("q", MethodFilter("search")),
        ("q_asn", "asn__startswith"),
    ]

    queryset = models.Network.objects.filter(status="ok")
    serializer_class = Serializers.net

    def filter_search(self, qset, value):
        return qset.filter(Q(name__icontains=value) | Q(asn__startswith=value))


@route
class Facility(DataViewSet):
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("org", "org_id"),
        ("country", "country"),
        ("city", "city"),
        ("q", "name__icontains"),
        ("asn", MethodFilter("asn")),
    ]

    queryset = models.Facility.objects.filter(status="ok")
    serializer_class = Serializers.fac

    def filter_asn(self, qset, value):
        """
        Returns all facilities that network specified by asn is peering at

        Arguments:

            qset - queryset
            value - asn
        """

        return qset.filter(netfac_set__net__asn=value).distinct("id")


@route
class NetworkIXLan(DataViewSet):
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("ix", "ixlan_id"),
        ("asn", "net__asn"),
        ("asns", "net__asn__in"),
        ("peers", MethodFilter("peers")),
        ("routeserver", MethodFilter("routeserver")),
    ]

    join_xl = {"ix": ("ixlan", "ixlan__ix")}

    queryset = models.NetworkIXLan.objects.filter(status="ok").select_related("net")
    serializer_class = Serializers.netixlan

    def filter_peers(self, qset, value):
        netixlan = self.get_queryset().filter(id=value).first()
        return qset.filter(ixlan_id=netixlan.ixlan_id, status="ok").exclude(id=value)

    def filter_routeserver(self, qset, value):
        if int(value):
            qset = qset.filter(net__info_type="Route Server")
        else:
            qset = qset.exclude(net__info_type="Route Server")
        return qset


@route
class NetworkContact(DataViewSet):
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("net", "net_id"),
        ("nets", "net_id__in"),
        ("asn", "net__asn"),
        ("asns", "net__asn__in"),
        ("role", "role__iexact"),
        ("roles", "role__in"),
        ("email", "email__iexact"),
        ("require_email", Exclude(Q(email="") | Q(email__isnull=True))),
    ]

    queryset = models.NetworkContact.objects.filter(status="ok")
    serializer_class = Serializers.poc


@route
class IXLanPrefix(DataViewSet):
    allowed_http_methods = ["GET"]
    valid_filters = [("ix", "ixlan_id"), ("prefix", "prefix")]

    queryset = models.IXLanPrefix.objects.filter(status="ok")
    serializer_class = Serializers.ixpfx


@route
class InternetExchangeFacility(DataViewSet):
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("ix", "ix_id"),
        ("fac", "fac_id"),
    ]

    queryset = models.InternetExchangeFacility.objects.filter(status="ok")
    serializer_class = Serializers.ixfac


@route
class NetworkFacility(DataViewSet):
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("net", "net_id"),
        ("fac", "fac_id"),
    ]

    queryset = models.NetworkFacility.objects.filter(status="ok")
    serializer_class = Serializers.netfac
