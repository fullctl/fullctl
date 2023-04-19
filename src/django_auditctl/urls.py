import fullctl.django.rest.urls.service_bridge_proxy as proxy
from django.urls import include, path

import django_auditctl.views as views

urlpatterns = proxy.urlpatterns(["aaactl", "devicectl"])

urlpatterns += [
    path(
        "api/",
        include(
            ("django_auditctl.rest.urls.auditctl", "auditctl_api"),
            namespace="auditctl_api",
        ),
    ),
    path("<str:org_tag>/", views.view_instance, name="auditctl-home"),
    path("", views.org_redirect),
]
