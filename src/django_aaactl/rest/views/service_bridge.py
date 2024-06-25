from django.contrib.auth import get_user_model
from fullctl.django.rest.core import BadRequest
from fullctl.django.rest.route.service_bridge import route
from fullctl.django.rest.views.service_bridge import DataViewSet, SystemViewSet, MethodFilter
from oauth2_provider.models import AccessToken
from rest_framework.decorators import action
from rest_framework.response import Response

import account.models as account_models
import applications.models as application_models
import billing.models as billing_models
import whitelabel_fullctl.models as branding_models
from common.rest.decorators import grainy_endpoint
from django_aaactl.rest.serializers.service_bridge import Serializers


class AaactlDataViewSet(DataViewSet):

    """
    Extend a new version of the data set view
    in order to use the aaactl grainy_endpoint decorator
    on the list and retrieve methods
    """

    @grainy_endpoint("service_bridge")
    def retrieve(self, request, pk):
        return self._retrieve(request, pk)

    @grainy_endpoint("service_bridge")
    def list(self, request, *args, **kwargs):
        return self._list(request, *args, **kwargs)

    @grainy_endpoint("service_bridge")
    def destroy(self, request, *args, **kwargs):
        return self._destroy(request, *args, **kwargs)

    @grainy_endpoint("service_bridge")
    def create(self, request, *args, **kwargs):
        print("REQUEST", request.data)
        return self._create(request, *args, **kwargs)


@route
class Heartbeat(SystemViewSet):
    ref_tag = "heartbeat"

    @grainy_endpoint("service_bridge.system", explicit=False)
    def list(self, request, *args, **kwargs):
        return Response({"status": "ok"})


@route
class Service(AaactlDataViewSet):
    path_prefix = "/data"
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("group", "group__iexact"),
        ("name", "name__iexact"),
        ("slug", "slug__iexact"),
    ]
    autocomplete = "name"
    allow_unfiltered = True

    queryset = application_models.Service.objects.filter(status="ok")
    serializer_class = Serializers.service_application

    def serializer_context(self, request, context):
        if request.GET.get("org"):
            org = account_models.Organization.objects.get(slug=request.GET.get("org"))
            context.update(org=org)

        return context

    @grainy_endpoint("service_bridge")
    def list(self, request, *args, **kwargs):

        qset = self.filter(self.get_queryset(), request)
        qset, joins = self.join_relations(qset, request)
        context = self.serializer_context(request, {"joins": joins})

        services = {svc.slug: svc for svc in qset}

        if context.get("org"):
            # loading for specific org, so we need to check if there
            # is service federation setup and replace the service
            # with the federated service

            for fed_svc_url in account_models.FederatedServiceURL.objects.filter(
                auth__org=context["org"]
            ):
                services[
                    fed_svc_url.service.slug
                ] = application_models.Service.from_federated_service_url(fed_svc_url)

        services = list(services.values())
        serializer = self.serializer_class(services, many=True, context=context)
        return Response(serializer.data)

    @action(
        detail=False,
        methods=["GET"],
        serializer_class=Serializers.organization_can_trial_for_object,
    )
    def trial_available(self, request, *args, **kwargs):
        serializer = Serializers.organization_can_trial_for_object(
            data=request.GET,
        )

        if not serializer.is_valid():
            return BadRequest(serializer.errors)

        return Response(serializer.data)

@route
class FederatedServiceURL(AaactlDataViewSet):
    path_prefix = "/data"
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("org", "auth__org__slug"),
        ("slug", "service__slug__iexact"),
        ("slugs", "service__slug__in"),
        ("tag", "tags__tag__iexact"),
        ("tags", "tags__tag__in"),
    ]
    autocomplete = "service"
    allow_unfiltered = True

    queryset = account_models.FederatedServiceURL.objects.all().select_related("service", "auth").prefetch_related("tags")
    serializer_class = Serializers.federated_service_url

@route
class Product(AaactlDataViewSet):
    path_prefix = "/data"
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("component", "component__name__iexact"),
        ("name", "name__iexact"),
    ]
    autocomplete = "name"
    allow_unfiltered = True

    queryset = billing_models.Product.objects.filter(status="ok")
    serializer_class = Serializers.product


@route
class OrganizationProduct(AaactlDataViewSet):
    path_prefix = "/data"
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("component", "product__component__name__iexact"),
        ("component_object_id", "subscription_product__component_object_id"),
        ("name", "product__name__iexact"),
        ("org", "org__slug"),
    ]
    autocomplete = "name"
    allow_unfiltered = True

    queryset = billing_models.OrganizationProduct.objects.filter(status="ok").order_by(
        "-created"
    )
    serializer_class = Serializers.org_product


@route
class User(AaactlDataViewSet):
    path_prefix = "/data"
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("username", "username__iexact"),
    ]
    allow_unfiltered = False
    autocomplete = "username"

    queryset = get_user_model().objects.all()
    serializer_class = Serializers.user


@route
class OauthAccessToken(AaactlDataViewSet):

    """
    Used to check if a given access token is still valid
    """

    path_prefix = "/data"
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("token", "token__iexact"),
    ]

    # do not allow unfiltered access to this endpoint
    # so the request needs to provide both the token
    # and an api key with appropriate service bridge permissions
    allow_unfiltered = False

    queryset = AccessToken.objects.all()
    serializer_class = Serializers.oauth_access_token


@route
class Impersonation(AaactlDataViewSet):
    path_prefix = "/data"
    allowed_http_methods = ["GET", "DELETE"]
    valid_filters = [
        ("superuser", "superuser"),
        ("user", "user"),
    ]
    allow_unfiltered = True

    queryset = account_models.Impersonation.objects.all()
    serializer_class = Serializers.impersonation


@route
class Contact(AaactlDataViewSet):
    path_prefix = "/data"
    allowed_http_methods = ["GET", "POST"]
    valid_filters = [
        ("name", "name__iexact"),
        ("email", "email__iexact"),
    ]
    allow_unfiltered = False
    autocomplete = "name"

    queryset = account_models.ContactMessage.objects.all()
    serializer_class = Serializers.contact_message


@route
class OrganizationBranding(AaactlDataViewSet):
    path_prefix = "/data"
    allowed_http_methods = ["GET"]
    valid_filters = [
        ("org", "org__slug"),
    ]
    allow_unfiltered = True

    queryset = branding_models.OrganizationBranding.objects.all()
    serializer_class = Serializers.org_branding
