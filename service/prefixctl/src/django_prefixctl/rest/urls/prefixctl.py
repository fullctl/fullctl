import django_prefixctl.rest.route.prefixctl
import django_prefixctl.rest.views.monitor
import django_prefixctl.rest.views.prefixctl
from django.urls import include, path

urlpatterns = [
    path("", include(django_prefixctl.rest.route.prefixctl.router.urls)),
]
