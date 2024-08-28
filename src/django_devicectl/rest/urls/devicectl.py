from django.urls import include, path

import django_devicectl.rest.route.devicectl
import django_devicectl.rest.views.devicectl
import django_devicectl.rest.views.sflow
import django_devicectl.rest.views.mrtg


urlpatterns = [
    path("", include(django_devicectl.rest.route.devicectl.router.urls)),
]
