import fullctl.django.rest.urls.service_bridge_proxy as service_bridge
from django.urls import include, path

import django_pdbctl.views as views

urlpatterns = service_bridge.urlpatterns(["aaactl", "devicectl"])

urlpatterns += [
    path("<str:org_tag>/", views.view_instance, name="pdbctl-home"),
    path("", views.org_redirect),
]
