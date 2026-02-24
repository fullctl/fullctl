import django_pdbctl.rest.route.pdbctl
import django_pdbctl.rest.views.pdbctl
from django.urls import include, path

urlpatterns = [
    path("", include(django_pdbctl.rest.route.pdbctl.router.urls)),
]
