from django.urls import include, path

import django_aclctl.rest.route.aclctl
import django_aclctl.rest.views.aclctl

urlpatterns = [
    path("", include(django_aclctl.rest.route.aclctl.router.urls)),
]
