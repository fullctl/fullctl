from django.urls import include, path

# import django_aclctl.rest.views
from django_aclctl import views

urlpatterns = [
    path(
        "api/",
        include(
            ("django_aclctl.rest.urls.aclctl", "aclctl_api"),
            namespace="aclctl_api",
        ),
    ),
    path("<str:org_tag>/", views.view_instance, name="aclctl-home"),
    path("", views.org_redirect),
]
