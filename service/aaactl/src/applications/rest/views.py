from rest_framework import viewsets
from rest_framework.response import Response

from applications.models import Service
from applications.rest.route import route
from applications.rest.serializers import Serializers


@route
class Services(viewsets.ViewSet):
    serializer_class = Serializers.service_application
    queryset = Serializers.service_application.Meta.model.objects.all()

    def list(self, request):
        services = []

        # if request has context for a specific org, check specifically for application
        # access for that org. Otherwise check for application access for any orgs.
        if request.selected_org:
            org_id = request.selected_org.id
        else:
            org_id = "?"

        for service in Service.objects.filter(status="ok").order_by("name"):
            if service.org_id and org_id != service.org_id:
                continue

            if service.always_show_dashboard or request.perms.check(
                service.Grainy.namespace(service) + f".{org_id}",
                "r",
                ignore_grant_all=True,
            ):
                services.append(service)

        serializer = Serializers.service_application(
            services,
            many=True,
        )

        return Response(serializer.data)
