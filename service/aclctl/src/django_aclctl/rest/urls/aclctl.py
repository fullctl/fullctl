import django_aclctl.rest.route.aclctl
import django_aclctl.rest.views.aclctl
from django.urls import include, path

urlpatterns = [
    path("", include(django_aclctl.rest.route.aclctl.router.urls)),
]
