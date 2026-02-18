from django.urls import include, path

import django_pdbctl.rest.route.pdbctl
import django_pdbctl.rest.views.pdbctl

urlpatterns = [
    path("", include(django_pdbctl.rest.route.pdbctl.router.urls)),
]
