import django_ixctl.rest.route.ixctl
import django_ixctl.rest.views.ixctl
from django.urls import include, path

urlpatterns = [
    path("", include(django_ixctl.rest.route.ixctl.router.urls)),
]
