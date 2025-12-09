from django.urls import include, path

import django_devicectl.views as views

# from django.views.generic import TemplateView


urlpatterns = [
    path(
        "api/",
        include(
            ("django_devicectl.rest.urls.devicectl", "devicectl_api"),
            namespace="devicectl_api",
        ),
    ),
    path(
        "<str:org_tag>/<str:facility_tag>/",
        views.view_instance_load_facility,
        name="devicectl-home",
    ),
    path("<str:org_tag>/", views.view_instance, name="devicectl-home"),
]
