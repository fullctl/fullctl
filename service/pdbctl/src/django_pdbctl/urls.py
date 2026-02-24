import django_pdbctl.views as views
from django.urls import path

import fullctl.django.rest.urls.service_bridge_proxy as service_bridge

urlpatterns = service_bridge.urlpatterns(["aaactl", "devicectl"])

urlpatterns += [
    path("<str:org_tag>/", views.view_instance, name="pdbctl-home"),
    path("", views.org_redirect),
]
